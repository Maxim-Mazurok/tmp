"""Live white-box physics calibration against the active FiveM fishing minigame.

This tool is separate from the main bot. It drives scripted input sequences,
captures the observed white-box trajectory, fits a simple box-physics model,
and overlays observed vs simulated motion in a dedicated debug window.
"""

from __future__ import annotations

import argparse
import csv
import ctypes
from dataclasses import asdict, dataclass
from datetime import datetime
import json
import os
import signal
import sys
import time

import cv2
import numpy as np
from scipy.optimize import minimize

sys.path.insert(0, '.')

from capture import ScreenCapture, find_game_window
from control import FishingController
from detection import BarDetector

import pydirectinput


pydirectinput.PAUSE = 0.0
pydirectinput.FAILSAFE = True

WINDOW_NAME = 'Live Box Physics Calibration'
WINDOW_WIDTH = 1500
WINDOW_HEIGHT = 980
WINDOW_MARGIN = 80
FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE = 0.5
FONT_THICKNESS = 1
PADDING = 10
PLOT_HEIGHT = 220
PANEL_WIDTH = 430
ZOOM = 4
DISPLAY_HZ = 15


def focus_game_window(game_win):
    """Bring the FiveM window to the foreground before sending scripted input."""
    user32 = ctypes.windll.user32
    hwnd = game_win['hwnd']
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    time.sleep(1.0)


def get_desktop_size() -> tuple[int, int]:
    """Return the current desktop resolution for initial window sizing."""
    user32 = ctypes.windll.user32
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def fit_window_size(image_width: int, image_height: int) -> tuple[int, int]:
    """Fit the OpenCV window to the rendered image without distorting its aspect ratio."""
    max_width, max_height = get_desktop_size()
    max_width = max(320, max_width - WINDOW_MARGIN)
    max_height = max(240, max_height - WINDOW_MARGIN)

    scale = min(max_width / max(image_width, 1), max_height / max(image_height, 1), 1.0)
    width = max(320, int(round(image_width * scale)))
    height = max(240, int(round(image_height * scale)))
    return width, height


@dataclass(frozen=True)
class PhysicsParams:
    """Simple one-dimensional box physics parameters.

    release_gravity: downward acceleration while space is released.
    hold_accel: upward acceleration magnitude while space is held.
    """

    release_gravity: float
    hold_accel: float

    @property
    def suggested_thrust(self) -> float:
        return self.release_gravity + self.hold_accel


@dataclass(frozen=True)
class Phase:
    """One input phase in an experiment."""

    mode: str
    duration: float
    duty: float | None = None
    label: str = ''


@dataclass(frozen=True)
class ExperimentSpec:
    """Scripted live-input experiment."""

    name: str
    phases: tuple[Phase, ...]
    description: str


@dataclass
class Sample:
    """One observed sample collected from the live game."""

    time: float
    dt: float
    hold: int
    duty: float
    box_center: float
    box_top: float
    box_bottom: float
    progress: float


DEFAULT_EXPERIMENTS = (
    ExperimentSpec(
        name='hold_0p5_release',
        description='Short upward pulse then coast',
        phases=(
            Phase('release', 0.40, label='settle'),
            Phase('hold', 0.50, label='hold 0.5s'),
            Phase('release', 1.50, label='observe release'),
        ),
    ),
    ExperimentSpec(
        name='hold_1p0_release',
        description='Medium upward pulse then coast',
        phases=(
            Phase('release', 0.40, label='settle'),
            Phase('hold', 1.00, label='hold 1.0s'),
            Phase('release', 1.80, label='observe release'),
        ),
    ),
    ExperimentSpec(
        name='hold_3p0_drop',
        description='Drive to the top then release to measure gravity',
        phases=(
            Phase('hold', 3.00, label='hold 3.0s'),
            Phase('release', 3.00, label='free fall'),
        ),
    ),
    ExperimentSpec(
        name='duty_35',
        description='Low duty PWM to probe near-fall behavior',
        phases=(Phase('duty', 2.50, duty=0.35, label='duty 35%'),),
    ),
    ExperimentSpec(
        name='duty_47',
        description='Hover duty probe near current model',
        phases=(Phase('duty', 2.50, duty=0.47, label='duty 47%'),),
    ),
    ExperimentSpec(
        name='duty_65',
        description='Aggressive duty PWM to probe sustained climb',
        phases=(Phase('duty', 2.50, duty=0.65, label='duty 65%'),),
    ),
)


def estimate_initial_velocity(samples: list[Sample], window: int = 4) -> float:
    """Estimate starting velocity from the first few observed samples."""
    if len(samples) < 2:
        return 0.0

    used = samples[:max(2, min(window, len(samples)))]
    dt = used[-1].time - used[0].time
    if dt <= 1e-6:
        return 0.0
    return (used[-1].box_center - used[0].box_center) / dt


def simulate_observed_sequence(samples: list[Sample], params: PhysicsParams,
                               initial_velocity: float | None = None) -> list[float]:
    """Simulate box center on the same timestamps and input sequence as observations."""
    if not samples:
        return []

    centers = [samples[0].box_center]
    box_center = samples[0].box_center
    box_velocity = estimate_initial_velocity(samples) if initial_velocity is None else initial_velocity

    for prev, current in zip(samples, samples[1:]):
        dt = max(current.dt, current.time - prev.time, 0.0)
        box_center, box_velocity = step_box_physics(
            box_center,
            box_velocity,
            bool(current.hold),
            dt,
            params,
        )

        centers.append(box_center)

    return centers


def step_box_physics(box_center: float, box_velocity: float, hold: bool,
                     dt: float, params: PhysicsParams) -> tuple[float, float]:
    """Advance the one-dimensional box model by one timestep."""
    accel = -params.hold_accel if hold else params.release_gravity
    box_velocity += accel * dt
    box_center += box_velocity * dt

    if box_center <= 0.0:
        return 0.0, 0.0
    if box_center >= 1.0:
        return 1.0, 0.0
    return box_center, box_velocity


def set_space_hold(hold: bool, last_hold: bool | None) -> bool:
    """Only emit key transitions when the scripted hold state changes."""
    if last_hold is hold:
        return hold

    if hold:
        pydirectinput.keyDown('space')
    else:
        pydirectinput.keyUp('space')
    return hold


def compute_rmse(samples: list[Sample], simulated_centers: list[float]) -> float:
    """Compute RMSE between observed and simulated box centers."""
    if not samples or not simulated_centers:
        return 0.0
    observed = np.array([sample.box_center for sample in samples], dtype=float)
    simulated = np.array(simulated_centers, dtype=float)
    if len(observed) != len(simulated):
        raise ValueError('Observed and simulated series must have the same length')
    return float(np.sqrt(np.mean((observed - simulated) ** 2)))


def fit_physics_params(experiments: list[dict], initial: PhysicsParams) -> tuple[PhysicsParams, float]:
    """Fit release gravity and hold acceleration to minimize trajectory RMSE."""
    usable = [entry for entry in experiments if len(entry.get('samples', [])) >= 3]
    if not usable:
        return initial, 0.0

    release_estimates = []
    hold_estimates = []
    for entry in usable:
        samples = entry['samples']
        for prev, current, nxt in zip(samples, samples[1:], samples[2:]):
            dt1 = max(current.time - prev.time, 1e-6)
            dt2 = max(nxt.time - current.time, 1e-6)
            if current.box_center in (0.0, 1.0):
                continue
            v1 = (current.box_center - prev.box_center) / dt1
            v2 = (nxt.box_center - current.box_center) / dt2
            accel = (v2 - v1) / max((dt1 + dt2) * 0.5, 1e-6)
            if current.hold:
                hold_estimates.append(-accel)
            else:
                release_estimates.append(accel)

    seeded_initial = PhysicsParams(
        release_gravity=float(np.median(release_estimates)) if release_estimates else initial.release_gravity,
        hold_accel=float(np.median(hold_estimates)) if hold_estimates else initial.hold_accel,
    )

    def objective(vector: np.ndarray) -> float:
        release_gravity = float(vector[0])
        hold_accel = float(vector[1])
        if release_gravity <= 0.0 or hold_accel <= 0.0:
            return 1e6

        params = PhysicsParams(release_gravity=release_gravity, hold_accel=hold_accel)
        total = 0.0
        for entry in usable:
            samples = entry['samples']
            simulated = simulate_observed_sequence(samples, params)
            rmse = compute_rmse(samples, simulated)
            total += rmse ** 2
        return total / max(len(usable), 1)

    starts = [
        np.array([initial.release_gravity, initial.hold_accel], dtype=float),
        np.array([seeded_initial.release_gravity, seeded_initial.hold_accel], dtype=float),
    ]
    best_result = None
    for start in starts:
        result = minimize(
            objective,
            start,
            method='L-BFGS-B',
            bounds=((0.5, 8.0), (0.5, 8.0)),
        )
        if best_result is None or result.fun < best_result.fun:
            best_result = result

    best = PhysicsParams(
        release_gravity=float(best_result.x[0]),
        hold_accel=float(best_result.x[1]),
    )
    return best, float(best_result.fun)


def phase_hold_state(phase: Phase, elapsed: float, accumulator: float) -> tuple[bool, float]:
    """Return the hold state for the current point in a phase."""
    if phase.mode == 'hold':
        return True, accumulator
    if phase.mode == 'release':
        return False, accumulator
    if phase.mode == 'duty':
        accumulator += float(phase.duty or 0.0)
        if accumulator >= 1.0:
            accumulator -= 1.0
            return True, accumulator
        return False, accumulator
    raise ValueError(f'Unknown phase mode: {phase.mode}')


def build_output_paths(root_dir: str | None) -> tuple[str, str, str]:
    """Create a timestamped output directory and return key output paths."""
    if root_dir is None:
        root_dir = os.path.join(os.path.dirname(__file__), 'live_physics_calibration')
    os.makedirs(root_dir, exist_ok=True)
    session_dir = os.path.join(root_dir, datetime.now().strftime('%Y%m%d_%H%M%S'))
    os.makedirs(session_dir, exist_ok=True)
    return (
        session_dir,
        os.path.join(session_dir, 'samples.csv'),
        os.path.join(session_dir, 'summary.json'),
    )


class LiveBoxPhysicsCalibrator:
    """Drive live-input experiments and fit a box-physics proxy model."""

    def __init__(self, output_dir=None, control_hz=FishingController.REFERENCE_HZ):
        self.control_hz = control_hz
        self.dt = 1.0 / control_hz
        self.output_dir, self.csv_path, self.summary_path = build_output_paths(output_dir)
        self.params = PhysicsParams(
            release_gravity=FishingController.GRAVITY,
            hold_accel=FishingController.THRUST - FishingController.GRAVITY,
        )
        self.fit_error = 0.0
        self.experiments: list[dict] = []

        self.game_win = find_game_window('fivem')
        if not self.game_win:
            raise RuntimeError('FiveM window not found')

        print(f"[*] Found game window: {self.game_win['title'][:60]}")
        focus_game_window(self.game_win)

        self.capture = ScreenCapture(game_window=self.game_win)
        self.detector = BarDetector()
        self._window_sized = False
        self._find_bar_or_raise()

    def _find_bar_or_raise(self):
        for _ in range(120):
            img, region = self.capture.capture_search_region()
            if self.detector.find_bar(img):
                self.detector.col_x1 += region['left']
                self.detector.col_x2 += region['left']
                self.detector.col_y1 += region['top']
                self.detector.col_y2 += region['top']
                self.detector.prog_x1 += region['left']
                self.detector.prog_x2 += region['left']
                return
            time.sleep(0.05)
        raise RuntimeError('Could not locate active fishing minigame bar')

    def _detect_frame(self):
        img, region = self.capture.capture_bar_region(self.detector)
        rel = BarDetector()
        rel.col_x1 = self.detector.col_x1 - region['left']
        rel.col_x2 = self.detector.col_x2 - region['left']
        rel.col_y1 = self.detector.col_y1 - region['top']
        rel.col_y2 = self.detector.col_y2 - region['top']
        rel.prog_x1 = self.detector.prog_x1 - region['left']
        rel.prog_x2 = self.detector.prog_x2 - region['left']
        rel.bar_found = True
        rel.fish_y_history = self.detector.fish_y_history
        rel.fish_y = self.detector.fish_y
        rel.box_top = self.detector.box_top
        rel.box_bottom = self.detector.box_bottom
        rel.box_center = self.detector.box_center

        result = rel.detect_elements(img)
        if result is None:
            return None

        self.detector.fish_y = rel.fish_y
        self.detector.box_top = rel.box_top
        self.detector.box_bottom = rel.box_bottom
        self.detector.box_center = rel.box_center
        self.detector.progress = rel.progress
        self.detector.fish_velocity = rel.fish_velocity
        self.detector.fish_y_history = rel.fish_y_history

        return img, region, rel

    def _draw_plot(self, width: int, height: int, samples: list[Sample], simulated: list[float]):
        canvas = np.zeros((height, width, 3), dtype=np.uint8)
        canvas[:, :] = (24, 24, 24)
        cv2.rectangle(canvas, (0, 0), (width - 1, height - 1), (70, 70, 70), 1)
        if len(samples) < 2:
            return canvas

        total_time = max(samples[-1].time, 1e-6)

        def to_point(idx: int, value: float):
            x = int((samples[idx].time / total_time) * (width - 20)) + 10
            y = int((1.0 - value) * (height - 20)) + 10
            return x, y

        observed_pts = np.array([to_point(i, sample.box_center) for i, sample in enumerate(samples)], dtype=np.int32)
        sim_pts = np.array([to_point(i, value) for i, value in enumerate(simulated)], dtype=np.int32)
        cv2.polylines(canvas, [observed_pts], False, (0, 220, 0), 2)
        cv2.polylines(canvas, [sim_pts], False, (0, 90, 255), 2)
        cv2.putText(canvas, 'Observed', (12, 18), FONT, 0.45, (0, 220, 0), 1)
        cv2.putText(canvas, 'Simulated', (100, 18), FONT, 0.45, (0, 90, 255), 1)
        return canvas

    def _compose_view(self, crop: np.ndarray, rel_detector: BarDetector, samples: list[Sample],
                      simulated: list[float], experiment: ExperimentSpec, phase: Phase,
                      hold: bool, phase_elapsed: float, experiment_elapsed: float):
        vis = rel_detector.draw_debug(crop)
        col_h = max(rel_detector.col_y2 - rel_detector.col_y1, 1)
        obs_y = rel_detector.col_y1 + int(rel_detector.box_center * col_h)
        cv2.line(vis, (rel_detector.col_x1 - 8, obs_y), (rel_detector.prog_x2 + 8, obs_y), (0, 220, 0), 2)

        if simulated:
            sim_y = rel_detector.col_y1 + int(simulated[-1] * col_h)
            cv2.line(vis, (rel_detector.col_x1 - 8, sim_y), (rel_detector.prog_x2 + 8, sim_y), (0, 90, 255), 2)

        zoomed = cv2.resize(vis, None, fx=ZOOM, fy=ZOOM, interpolation=cv2.INTER_NEAREST)
        plot = self._draw_plot(zoomed.shape[1], PLOT_HEIGHT, samples, simulated)

        left = np.vstack([zoomed, plot])
        panel = np.zeros((left.shape[0], PANEL_WIDTH, 3), dtype=np.uint8)
        panel[:, :] = (35, 35, 35)

        rmse = compute_rmse(samples, simulated) if simulated else 0.0
        lines = [
            f'Experiment   {experiment.name}',
            f'Description  {experiment.description}',
            f'Phase        {phase.label or phase.mode}',
            f'Phase t      {phase_elapsed:5.2f}s / {phase.duration:4.2f}s',
            f'Exp t        {experiment_elapsed:5.2f}s',
            f'Input        {"HOLD" if hold else "RELEASE"}',
            f'Loop dt      {samples[-1].dt * 1000:6.1f} ms' if samples else 'Loop dt      n/a',
            f'Observed box {rel_detector.box_center:6.3f}',
            f'Simulated box {simulated[-1] if simulated else float("nan"):6.3f}',
            f'RMSE         {rmse:7.4f}',
            '',
            f'Fit gravity  {self.params.release_gravity:7.4f}',
            f'Fit hold acc {self.params.hold_accel:7.4f}',
            f'Suggest thrust {self.params.suggested_thrust:7.4f}',
            f'Global loss  {self.fit_error:7.5f}',
            '',
            f'Samples      {len(samples):4d}',
            f'Output dir   {os.path.basename(self.output_dir)}',
            '',
            'Keys: q abort, close window abort',
        ]
        y = 24
        for line in lines:
            cv2.putText(panel, line, (PADDING, y), FONT, FONT_SCALE, (235, 235, 235), FONT_THICKNESS)
            y += 22

        return np.hstack([left, panel])

    def _write_samples_csv(self):
        rows = []
        for experiment in self.experiments:
            for sample in experiment['samples']:
                row = asdict(sample)
                row['experiment'] = experiment['name']
                rows.append(row)

        with open(self.csv_path, 'w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                'experiment', 'time', 'dt', 'hold', 'duty', 'box_center',
                'box_top', 'box_bottom', 'progress',
            ])
            writer.writeheader()
            writer.writerows(rows)

    def _write_summary(self):
        payload = {
            'params': {
                'release_gravity': self.params.release_gravity,
                'hold_accel': self.params.hold_accel,
                'suggested_thrust': self.params.suggested_thrust,
            },
            'fit_error': self.fit_error,
            'experiments': [
                {
                    'name': entry['name'],
                    'description': entry['description'],
                    'rmse': entry.get('rmse', 0.0),
                    'samples': len(entry['samples']),
                }
                for entry in self.experiments
            ],
        }
        with open(self.summary_path, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, indent=2)

    def _fit_all(self):
        self.params, self.fit_error = fit_physics_params(self.experiments, self.params)
        for entry in self.experiments:
            simulated = simulate_observed_sequence(entry['samples'], self.params)
            entry['rmse'] = compute_rmse(entry['samples'], simulated)

    def run_experiment(self, experiment: ExperimentSpec):
        samples: list[Sample] = []
        simulated: list[float] = []
        simulated_velocity = 0.0
        accumulator = 0.0
        pydirectinput.keyUp('space')
        last_hold = False
        last_t = None
        last_display_t = 0.0
        display_interval = 1.0 / DISPLAY_HZ
        experiment_start = time.perf_counter()

        for phase in experiment.phases:
            phase_start = time.perf_counter()
            while True:
                loop_start = time.perf_counter()
                phase_elapsed = loop_start - phase_start
                experiment_elapsed = loop_start - experiment_start
                if phase_elapsed >= phase.duration:
                    break

                hold, accumulator = phase_hold_state(phase, phase_elapsed, accumulator)
                last_hold = set_space_hold(hold, last_hold)

                detected = self._detect_frame()
                if detected is None:
                    time.sleep(self.dt)
                    continue

                crop, region, rel_detector = detected
                dt = self.dt if last_t is None else max(loop_start - last_t, 1e-4)
                last_t = loop_start

                duty = float(phase.duty or (1.0 if hold else 0.0))
                samples.append(Sample(
                    time=experiment_elapsed,
                    dt=dt,
                    hold=int(hold),
                    duty=duty,
                    box_center=rel_detector.box_center,
                    box_top=rel_detector.box_top,
                    box_bottom=rel_detector.box_bottom,
                    progress=rel_detector.progress,
                ))

                if len(samples) == 1:
                    simulated = [samples[0].box_center]
                    simulated_velocity = 0.0
                else:
                    if len(samples) == 2:
                        simulated_velocity = estimate_initial_velocity(samples[:2], window=2)
                    next_center, simulated_velocity = step_box_physics(
                        simulated[-1],
                        simulated_velocity,
                        hold,
                        dt,
                        self.params,
                    )
                    simulated.append(next_center)

                if (loop_start - last_display_t) >= display_interval:
                    display = self._compose_view(
                        crop, rel_detector, samples, simulated,
                        experiment, phase, hold, phase_elapsed, experiment_elapsed,
                    )
                    if not self._window_sized:
                        window_width, window_height = fit_window_size(display.shape[1], display.shape[0])
                        cv2.resizeWindow(WINDOW_NAME, window_width, window_height)
                        self._window_sized = True
                    cv2.imshow(WINDOW_NAME, display)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        raise KeyboardInterrupt
                    last_display_t = loop_start

                sleep_time = self.dt - (time.perf_counter() - loop_start)
                if sleep_time > 0:
                    time.sleep(sleep_time)

        pydirectinput.keyUp('space')
        entry = {
            'name': experiment.name,
            'description': experiment.description,
            'samples': samples,
        }
        self.experiments.append(entry)
        self._fit_all()
        self._write_samples_csv()
        self._write_summary()

    def run(self, experiments=DEFAULT_EXPERIMENTS):
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
        cv2.resizeWindow(WINDOW_NAME, WINDOW_WIDTH, WINDOW_HEIGHT)
        print(f'[*] Writing calibration outputs to {self.output_dir}')
        for experiment in experiments:
            print(f'[*] Running {experiment.name}: {experiment.description}')
            self.run_experiment(experiment)
            print(
                f"    fit gravity={self.params.release_gravity:.4f} "
                f"hold_accel={self.params.hold_accel:.4f} "
                f"suggested_thrust={self.params.suggested_thrust:.4f}"
            )


def main():
    parser = argparse.ArgumentParser(description='Calibrate live white-box physics against the active FiveM minigame')
    parser.add_argument('--output-dir', type=str, default=None, help='Optional output directory root')
    args = parser.parse_args()

    calibrator = LiveBoxPhysicsCalibrator(output_dir=args.output_dir)

    def _shutdown(*_):
        pydirectinput.keyUp('space')
        cv2.destroyAllWindows()
        raise SystemExit(1)

    signal.signal(signal.SIGINT, _shutdown)

    try:
        calibrator.run()
    finally:
        pydirectinput.keyUp('space')
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()