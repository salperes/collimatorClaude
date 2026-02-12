"""Analytic projection engine — geometric projection of test objects.

Calculates detector intensity profiles and MTF for wire, line-pair,
and grid phantoms using geometric magnification, Beer-Lambert
attenuation, and focal spot blur (PSF convolution).

All internal calculations in core units (cm, keV).
UI-facing results use mm for positions, lp/mm for frequencies.

Reference: Phase-03.5 spec — Phantom Projection.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import gaussian_filter1d, uniform_filter1d

from app.core.units import mm_to_cm, cm_to_mm
from app.models.phantom import (
    AnyPhantom,
    GridPhantom,
    LinePairPhantom,
    PhantomType,
    ProjectionMethod,
    WirePhantom,
)
from app.models.projection import (
    DetectorProfile,
    GeometricParams,
    MTFResult,
    ProjectionResult,
)

if TYPE_CHECKING:
    from app.core.physics_engine import PhysicsEngine
    from app.models.geometry import FocalSpotDistribution


class ProjectionEngine:
    """Analytic projection calculator.

    Uses geometric optics (point/extended source), Beer-Lambert attenuation,
    and PSF convolution to compute detector intensity profiles.

    Args:
        physics_engine: PhysicsEngine for linear attenuation lookups.
    """

    def __init__(self, physics_engine: PhysicsEngine) -> None:
        self._physics = physics_engine

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate_geometry(
        self,
        src_y_cm: float,
        obj_y_cm: float,
        det_y_cm: float,
        focal_spot_cm: float,
    ) -> GeometricParams:
        """Compute projection geometry parameters.

        All inputs and outputs in cm.

        Args:
            src_y_cm: Source Y position [cm].
            obj_y_cm: Object Y position [cm].
            det_y_cm: Detector Y position [cm].
            focal_spot_cm: Focal spot diameter [cm].

        Returns:
            GeometricParams with SOD, ODD, SDD, M, Ug.
        """
        sod = abs(obj_y_cm - src_y_cm)
        odd = abs(det_y_cm - obj_y_cm)
        sdd = abs(det_y_cm - src_y_cm)

        if sod < 1e-10:
            return GeometricParams(
                sod_cm=sod, odd_cm=odd, sdd_cm=sdd,
                magnification=1.0, geometric_unsharpness_cm=0.0,
            )

        magnification = sdd / sod
        ug = focal_spot_cm * odd / sod

        return GeometricParams(
            sod_cm=sod,
            odd_cm=odd,
            sdd_cm=sdd,
            magnification=magnification,
            geometric_unsharpness_cm=ug,
        )

    def project_wire(
        self,
        wire: WirePhantom,
        src_y_mm: float,
        det_y_mm: float,
        focal_spot_mm: float,
        focal_spot_dist: FocalSpotDistribution,
        energy_keV: float,
        num_samples: int = 1000,
    ) -> ProjectionResult:
        """Project a wire phantom onto the detector plane.

        Circular cross-section: chord length at lateral position x is
        2 * sqrt(r^2 - x^2) for |x| < r, where r = wire radius.

        Args:
            wire: Wire phantom configuration.
            src_y_mm: Source Y position [mm].
            det_y_mm: Detector Y position [mm].
            focal_spot_mm: Focal spot diameter [mm].
            focal_spot_dist: Focal spot distribution type.
            energy_keV: Photon energy [keV].
            num_samples: Number of detector sample points.

        Returns:
            ProjectionResult with detector profile and MTF.
        """
        obj_y_mm = wire.config.position_y
        material_id = wire.config.material_id
        diameter_mm = wire.diameter

        # Convert to core units
        src_y_cm = float(mm_to_cm(src_y_mm))
        obj_y_cm = float(mm_to_cm(obj_y_mm))
        det_y_cm = float(mm_to_cm(det_y_mm))
        focal_cm = float(mm_to_cm(focal_spot_mm))
        radius_cm = float(mm_to_cm(diameter_mm / 2.0))

        geo = self.calculate_geometry(src_y_cm, obj_y_cm, det_y_cm, focal_cm)

        # Projected wire radius at detector plane
        proj_radius_cm = radius_cm * geo.magnification

        # Build detector position array (centered on wire projection)
        # Span = 4x projected radius + 4x Ug (for PSF tails)
        span_cm = max(4.0 * proj_radius_cm + 4.0 * geo.geometric_unsharpness_cm, 0.1)
        x_cm = np.linspace(-span_cm, span_cm, num_samples)
        dx_cm = x_cm[1] - x_cm[0] if len(x_cm) > 1 else 1e-6

        # μ for the wire material
        mu_cm = self._physics.linear_attenuation(material_id, energy_keV)

        # Chord length through circular cross-section at each detector position
        # Map detector position back to object plane: x_obj = x_det / M
        x_obj = x_cm / geo.magnification
        r2 = radius_cm ** 2
        x2 = x_obj ** 2
        inside = x2 < r2
        chord = np.zeros_like(x_cm)
        chord[inside] = 2.0 * np.sqrt(r2 - x2[inside])

        # Beer-Lambert transmission through wire
        intensities = np.exp(-mu_cm * chord)

        # Apply focal spot blur (PSF convolution)
        intensities = self._apply_psf(
            intensities, geo.geometric_unsharpness_cm, dx_cm, focal_spot_dist,
        )

        # Convert positions to mm for output
        positions_mm = np.array([float(cm_to_mm(x)) for x in x_cm])

        # Contrast
        contrast = self._michelson_contrast(intensities)

        profile = DetectorProfile(
            positions_mm=positions_mm,
            intensities=intensities,
            contrast=contrast,
        )

        # MTF from LSF (the wire projection IS the LSF for a thin wire)
        mtf = self._compute_mtf_from_lsf(intensities, dx_cm, geo.magnification)

        return ProjectionResult(
            phantom_id=wire.config.id,
            method=ProjectionMethod.ANALYTIC,
            geometry=geo,
            profile=profile,
            mtf=mtf,
        )

    def project_line_pair(
        self,
        lp: LinePairPhantom,
        src_y_mm: float,
        det_y_mm: float,
        focal_spot_mm: float,
        focal_spot_dist: FocalSpotDistribution,
        energy_keV: float,
        num_samples: int = 2000,
    ) -> ProjectionResult:
        """Project a line-pair (bar pattern) phantom onto the detector plane.

        Alternating opaque bars and transparent spaces at a given frequency.

        Args:
            lp: Line-pair phantom configuration.
            src_y_mm: Source Y position [mm].
            det_y_mm: Detector Y position [mm].
            focal_spot_mm: Focal spot diameter [mm].
            focal_spot_dist: Focal spot distribution type.
            energy_keV: Photon energy [keV].
            num_samples: Number of detector sample points.

        Returns:
            ProjectionResult with detector profile and MTF.
        """
        obj_y_mm = lp.config.position_y
        material_id = lp.config.material_id
        freq_lpmm = lp.frequency
        bar_thickness_mm = lp.bar_thickness
        num_cycles = lp.num_cycles

        # Convert to core units
        src_y_cm = float(mm_to_cm(src_y_mm))
        obj_y_cm = float(mm_to_cm(obj_y_mm))
        det_y_cm = float(mm_to_cm(det_y_mm))
        focal_cm = float(mm_to_cm(focal_spot_mm))
        bar_thickness_cm = float(mm_to_cm(bar_thickness_mm))

        geo = self.calculate_geometry(src_y_cm, obj_y_cm, det_y_cm, focal_cm)

        # Bar width at object plane: 1 cycle = bar + space = 1/freq [mm] -> cm
        cycle_width_cm = float(mm_to_cm(1.0 / freq_lpmm)) if freq_lpmm > 0 else 1.0
        bar_width_cm = cycle_width_cm / 2.0

        # Total pattern width at object plane
        pattern_width_cm = num_cycles * cycle_width_cm
        # Add margins for PSF tails
        margin_cm = 3.0 * geo.geometric_unsharpness_cm + cycle_width_cm
        total_width_cm = pattern_width_cm + 2 * margin_cm

        # Projected onto detector plane
        total_proj_cm = total_width_cm * geo.magnification
        x_cm = np.linspace(-total_proj_cm / 2, total_proj_cm / 2, num_samples)
        dx_cm = x_cm[1] - x_cm[0] if len(x_cm) > 1 else 1e-6

        # Map back to object plane
        x_obj = x_cm / geo.magnification

        # μ for bar material
        mu_cm = self._physics.linear_attenuation(material_id, energy_keV)

        # Build square wave: bar at odd half-cycles, space at even
        # Pattern centered at x=0
        pattern_half = pattern_width_cm / 2.0
        # Position within pattern
        x_rel = x_obj + pattern_half  # shift so pattern starts at 0
        in_pattern = (x_rel >= 0) & (x_rel < pattern_width_cm)

        # Within pattern: bar if in first half of cycle
        cycle_pos = np.mod(x_rel, cycle_width_cm)
        is_bar = in_pattern & (cycle_pos < bar_width_cm)

        # Beer-Lambert
        thickness = np.where(is_bar, bar_thickness_cm, 0.0)
        intensities = np.exp(-mu_cm * thickness)

        # PSF blur
        intensities = self._apply_psf(
            intensities, geo.geometric_unsharpness_cm, dx_cm, focal_spot_dist,
        )

        positions_mm = np.array([float(cm_to_mm(x)) for x in x_cm])
        contrast = self._michelson_contrast(intensities)

        profile = DetectorProfile(
            positions_mm=positions_mm,
            intensities=intensities,
            contrast=contrast,
        )

        # MTF via FFT of the full profile
        mtf = self._compute_mtf_from_profile(intensities, dx_cm, geo.magnification)

        return ProjectionResult(
            phantom_id=lp.config.id,
            method=ProjectionMethod.ANALYTIC,
            geometry=geo,
            profile=profile,
            mtf=mtf,
        )

    def project_grid(
        self,
        grid: GridPhantom,
        src_y_mm: float,
        det_y_mm: float,
        focal_spot_mm: float,
        focal_spot_dist: FocalSpotDistribution,
        energy_keV: float,
        num_samples: int = 1000,
    ) -> ProjectionResult:
        """Project a grid phantom (1D slice) onto the detector plane.

        The grid is modeled as periodic wires at the given pitch.

        Args:
            grid: Grid phantom configuration.
            src_y_mm: Source Y position [mm].
            det_y_mm: Detector Y position [mm].
            focal_spot_mm: Focal spot diameter [mm].
            focal_spot_dist: Focal spot distribution type.
            energy_keV: Photon energy [keV].
            num_samples: Number of detector sample points.

        Returns:
            ProjectionResult with detector profile and MTF.
        """
        obj_y_mm = grid.config.position_y
        material_id = grid.config.material_id

        # Convert to core units
        src_y_cm = float(mm_to_cm(src_y_mm))
        obj_y_cm = float(mm_to_cm(obj_y_mm))
        det_y_cm = float(mm_to_cm(det_y_mm))
        focal_cm = float(mm_to_cm(focal_spot_mm))
        pitch_cm = float(mm_to_cm(grid.pitch))
        wire_r_cm = float(mm_to_cm(grid.wire_diameter / 2.0))
        size_cm = float(mm_to_cm(grid.size))

        geo = self.calculate_geometry(src_y_cm, obj_y_cm, det_y_cm, focal_cm)

        # Span at detector
        proj_size_cm = size_cm * geo.magnification
        margin_cm = 3.0 * geo.geometric_unsharpness_cm + pitch_cm * geo.magnification
        total_span_cm = proj_size_cm + 2 * margin_cm
        x_cm = np.linspace(-total_span_cm / 2, total_span_cm / 2, num_samples)
        dx_cm = x_cm[1] - x_cm[0] if len(x_cm) > 1 else 1e-6

        # Map back to object
        x_obj = x_cm / geo.magnification

        mu_cm = self._physics.linear_attenuation(material_id, energy_keV)

        # For each detector position, sum chord lengths through all wires
        # Wire centers at 0, ±pitch, ±2*pitch, ... within grid extent
        half_size = size_cm / 2.0
        n_wires = int(half_size / pitch_cm) + 1 if pitch_cm > 0 else 0
        wire_centers = []
        for i in range(-n_wires, n_wires + 1):
            wc = i * pitch_cm
            if abs(wc) <= half_size + wire_r_cm:
                wire_centers.append(wc)

        total_chord = np.zeros_like(x_obj)
        r2 = wire_r_cm ** 2
        for wc in wire_centers:
            dx_from_center = x_obj - wc
            d2 = dx_from_center ** 2
            inside = d2 < r2
            total_chord[inside] += 2.0 * np.sqrt(r2 - d2[inside])

        intensities = np.exp(-mu_cm * total_chord)

        intensities = self._apply_psf(
            intensities, geo.geometric_unsharpness_cm, dx_cm, focal_spot_dist,
        )

        positions_mm = np.array([float(cm_to_mm(x)) for x in x_cm])
        contrast = self._michelson_contrast(intensities)

        profile = DetectorProfile(
            positions_mm=positions_mm,
            intensities=intensities,
            contrast=contrast,
        )

        mtf = self._compute_mtf_from_profile(intensities, dx_cm, geo.magnification)

        return ProjectionResult(
            phantom_id=grid.config.id,
            method=ProjectionMethod.ANALYTIC,
            geometry=geo,
            profile=profile,
            mtf=mtf,
        )

    def project(
        self,
        phantom: AnyPhantom,
        src_y_mm: float,
        det_y_mm: float,
        focal_spot_mm: float,
        focal_spot_dist: FocalSpotDistribution,
        energy_keV: float,
    ) -> ProjectionResult:
        """Dispatch projection to the appropriate phantom type handler.

        Args:
            phantom: Any phantom type.
            src_y_mm: Source Y position [mm].
            det_y_mm: Detector Y position [mm].
            focal_spot_mm: Focal spot diameter [mm].
            focal_spot_dist: Focal spot distribution type.
            energy_keV: Photon energy [keV].

        Returns:
            ProjectionResult.
        """
        if isinstance(phantom, WirePhantom):
            return self.project_wire(
                phantom, src_y_mm, det_y_mm,
                focal_spot_mm, focal_spot_dist, energy_keV,
            )
        elif isinstance(phantom, LinePairPhantom):
            return self.project_line_pair(
                phantom, src_y_mm, det_y_mm,
                focal_spot_mm, focal_spot_dist, energy_keV,
            )
        elif isinstance(phantom, GridPhantom):
            return self.project_grid(
                phantom, src_y_mm, det_y_mm,
                focal_spot_mm, focal_spot_dist, energy_keV,
            )
        else:
            raise ValueError(f"Unknown phantom type: {type(phantom)}")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _apply_psf(
        self,
        intensities: NDArray[np.float64],
        ug_cm: float,
        dx_cm: float,
        focal_spot_dist: FocalSpotDistribution,
    ) -> NDArray[np.float64]:
        """Apply focal spot point-spread function via convolution.

        Args:
            intensities: Input intensity array.
            ug_cm: Geometric unsharpness [cm].
            dx_cm: Sampling interval [cm].
            focal_spot_dist: Distribution type (UNIFORM or GAUSSIAN).

        Returns:
            Blurred intensity array.
        """
        from app.models.geometry import FocalSpotDistribution

        if ug_cm < dx_cm or ug_cm < 1e-10:
            return intensities

        if focal_spot_dist == FocalSpotDistribution.GAUSSIAN:
            # FWHM = Ug, sigma = FWHM / (2 * sqrt(2 * ln(2))) ≈ FWHM / 2.355
            sigma_cm = ug_cm / 2.355
            sigma_samples = sigma_cm / dx_cm
            if sigma_samples > 0.5:
                return gaussian_filter1d(intensities, sigma=sigma_samples, mode='nearest')
        else:
            # Uniform (rect) PSF
            width_samples = int(round(ug_cm / dx_cm))
            if width_samples >= 2:
                return uniform_filter1d(intensities, size=width_samples, mode='nearest')

        return intensities

    @staticmethod
    def _michelson_contrast(intensities: NDArray[np.float64]) -> float:
        """Michelson contrast: (Imax - Imin) / (Imax + Imin).

        Args:
            intensities: Intensity array.

        Returns:
            Contrast in [0, 1].
        """
        i_max = float(np.max(intensities))
        i_min = float(np.min(intensities))
        denom = i_max + i_min
        if denom < 1e-30:
            return 0.0
        return (i_max - i_min) / denom

    def _compute_mtf_from_lsf(
        self,
        intensities: NDArray[np.float64],
        dx_cm: float,
        magnification: float,
    ) -> MTFResult:
        """Compute MTF from a wire (LSF) projection.

        The wire projection approximates the Line Spread Function.
        MTF = |FFT(LSF)| normalized to MTF(0) = 1.

        The LSF is derived as: 1 - intensity profile (absorption dip).

        Args:
            intensities: Detector intensity profile.
            dx_cm: Sampling interval [cm].
            magnification: Geometric magnification.

        Returns:
            MTFResult.
        """
        # LSF = absorption signal (inverted: 1 - I)
        # Do NOT subtract mean — DC component needed for normalization
        lsf = 1.0 - intensities

        return self._fft_to_mtf(lsf, dx_cm, magnification)

    def _compute_mtf_from_profile(
        self,
        intensities: NDArray[np.float64],
        dx_cm: float,
        magnification: float,
    ) -> MTFResult:
        """Compute MTF from a general intensity profile via FFT.

        For bar-pattern / grid profiles, we compute the modulation
        spectrum normalized by the DC (mean) component.

        Args:
            intensities: Detector intensity profile.
            dx_cm: Sampling interval [cm].
            magnification: Geometric magnification.

        Returns:
            MTFResult.
        """
        # Use absorption signal (1 - I) like LSF method
        signal = 1.0 - intensities

        return self._fft_to_mtf(signal, dx_cm, magnification)

    def _fft_to_mtf(
        self,
        signal: NDArray[np.float64],
        dx_cm: float,
        magnification: float,
    ) -> MTFResult:
        """Convert signal to MTF via FFT.

        Args:
            signal: Input signal (mean-subtracted).
            dx_cm: Sampling interval [cm].
            magnification: Geometric magnification.

        Returns:
            MTFResult with frequencies in lp/mm at object plane.
        """
        n = len(signal)
        if n < 4:
            return MTFResult()

        # FFT
        spectrum = np.abs(np.fft.rfft(signal))

        # Normalize: MTF(0) = 1
        if spectrum[0] > 1e-30:
            mtf_values = spectrum / spectrum[0]
        else:
            # Fallback: normalize to max
            s_max = np.max(spectrum)
            mtf_values = spectrum / s_max if s_max > 1e-30 else spectrum

        # Frequency axis at detector plane [cycles/cm]
        freq_det_per_cm = np.fft.rfftfreq(n, d=dx_cm)

        # Convert to object plane: f_obj = f_det * M
        # Then convert to lp/mm: [cycles/cm] / M × (1 cm / 10 mm)
        # f_obj [lp/mm] = freq_det_per_cm / M / 10
        # Actually: f_obj [cycles/cm] = f_det [cycles/cm] * M (demagnify)
        # f_obj [lp/mm] = f_obj [cycles/cm] / 10
        # Wait: The projection magnifies the object by M, so frequencies
        # at detector are lower by factor M:
        # f_det = f_obj / M => f_obj = f_det * M
        freq_obj_per_cm = freq_det_per_cm * magnification
        freq_obj_lpmm = freq_obj_per_cm / 10.0  # cm^-1 to mm^-1

        # Find MTF@50% and MTF@10% frequencies
        mtf_50 = self._find_mtf_frequency(freq_obj_lpmm, mtf_values, 0.5)
        mtf_10 = self._find_mtf_frequency(freq_obj_lpmm, mtf_values, 0.1)

        return MTFResult(
            frequencies_lpmm=freq_obj_lpmm,
            mtf_values=mtf_values,
            mtf_50_freq=mtf_50,
            mtf_10_freq=mtf_10,
        )

    @staticmethod
    def _find_mtf_frequency(
        frequencies: NDArray[np.float64],
        mtf_values: NDArray[np.float64],
        threshold: float,
    ) -> float:
        """Find frequency where MTF crosses a threshold.

        Args:
            frequencies: Frequency axis [lp/mm].
            mtf_values: MTF values.
            threshold: MTF threshold (e.g. 0.5, 0.1).

        Returns:
            Frequency [lp/mm] where MTF first drops below threshold,
            0.0 if never drops below.
        """
        if len(frequencies) < 2 or len(mtf_values) < 2:
            return 0.0

        # Skip DC (index 0)
        for i in range(1, len(mtf_values)):
            if mtf_values[i] < threshold:
                # Linear interpolation
                if i > 0 and mtf_values[i - 1] >= threshold:
                    f0, f1 = frequencies[i - 1], frequencies[i]
                    m0, m1 = mtf_values[i - 1], mtf_values[i]
                    dm = m0 - m1
                    if dm > 1e-30:
                        frac = (m0 - threshold) / dm
                        return float(f0 + frac * (f1 - f0))
                return float(frequencies[i])

        return 0.0
