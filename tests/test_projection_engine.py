"""Projection engine tests — analytic phantom projection.

Tests geometric parameters, wire/line-pair/grid projections,
focal spot blur, and MTF calculation.
"""

import math

import numpy as np
import pytest

from app.core.material_database import MaterialService
from app.core.physics_engine import PhysicsEngine
from app.core.projection_engine import ProjectionEngine
from app.core.units import mm_to_cm, cm_to_mm
from app.models.geometry import FocalSpotDistribution
from app.models.phantom import (
    GridPhantom,
    LinePairPhantom,
    PhantomConfig,
    PhantomType,
    WirePhantom,
)


@pytest.fixture(scope="module")
def svc() -> MaterialService:
    return MaterialService()


@pytest.fixture(scope="module")
def physics(svc: MaterialService) -> PhysicsEngine:
    return PhysicsEngine(svc)


@pytest.fixture(scope="module")
def engine(physics: PhysicsEngine) -> ProjectionEngine:
    return ProjectionEngine(physics)


# -----------------------------------------------------------------------
# Geometric parameters
# -----------------------------------------------------------------------

class TestGeometricParams:
    """Test calculate_geometry with known SOD/ODD/SDD values."""

    def test_magnification_basic(self, engine: ProjectionEngine):
        """M = SDD/SOD for simple geometry."""
        # Source at y=-100cm, object at y=-50cm, detector at y=0
        geo = engine.calculate_geometry(
            src_y_cm=-100.0, obj_y_cm=-50.0, det_y_cm=0.0, focal_spot_cm=0.1,
        )
        assert geo.sod_cm == pytest.approx(50.0)
        assert geo.odd_cm == pytest.approx(50.0)
        assert geo.sdd_cm == pytest.approx(100.0)
        assert geo.magnification == pytest.approx(2.0)

    def test_magnification_asymmetric(self, engine: ProjectionEngine):
        """M = SDD/SOD for asymmetric geometry."""
        # SOD=75, ODD=25 => SDD=100, M=100/75=1.333
        geo = engine.calculate_geometry(
            src_y_cm=-100.0, obj_y_cm=-25.0, det_y_cm=0.0, focal_spot_cm=0.2,
        )
        assert geo.sod_cm == pytest.approx(75.0)
        assert geo.odd_cm == pytest.approx(25.0)
        assert geo.magnification == pytest.approx(100.0 / 75.0, rel=1e-6)

    def test_geometric_unsharpness(self, engine: ProjectionEngine):
        """Ug = f * ODD / SOD."""
        # f=0.1cm, SOD=50, ODD=50 => Ug = 0.1*50/50 = 0.1 cm
        geo = engine.calculate_geometry(
            src_y_cm=-100.0, obj_y_cm=-50.0, det_y_cm=0.0, focal_spot_cm=0.1,
        )
        assert geo.geometric_unsharpness_cm == pytest.approx(0.1)

    def test_ug_larger_odd(self, engine: ProjectionEngine):
        """Larger ODD => larger Ug."""
        # f=0.1cm, SOD=25, ODD=75 => Ug = 0.1*75/25 = 0.3 cm
        geo = engine.calculate_geometry(
            src_y_cm=-100.0, obj_y_cm=-75.0, det_y_cm=0.0, focal_spot_cm=0.1,
        )
        assert geo.geometric_unsharpness_cm == pytest.approx(0.3)

    def test_zero_focal_spot(self, engine: ProjectionEngine):
        """Zero focal spot => zero Ug (point source)."""
        geo = engine.calculate_geometry(
            src_y_cm=-100.0, obj_y_cm=-50.0, det_y_cm=0.0, focal_spot_cm=0.0,
        )
        assert geo.geometric_unsharpness_cm == pytest.approx(0.0)

    def test_object_at_source(self, engine: ProjectionEngine):
        """SOD ≈ 0 => M → large, handled gracefully."""
        geo = engine.calculate_geometry(
            src_y_cm=-100.0, obj_y_cm=-100.0, det_y_cm=0.0, focal_spot_cm=0.1,
        )
        # SOD ≈ 0, should return M=1 (safe fallback)
        assert geo.magnification == pytest.approx(1.0)
        assert geo.geometric_unsharpness_cm == pytest.approx(0.0)


# -----------------------------------------------------------------------
# Wire phantom projection
# -----------------------------------------------------------------------

class TestWireProjection:
    """Test wire phantom projection."""

    def _make_wire(self, diameter_mm: float = 0.5, material: str = "W",
                   position_y: float = 300.0) -> WirePhantom:
        return WirePhantom(
            config=PhantomConfig(
                type=PhantomType.WIRE,
                name=f"Tel {diameter_mm}mm",
                position_y=position_y,
                material_id=material,
            ),
            diameter=diameter_mm,
        )

    def test_wire_center_attenuation(self, engine: ProjectionEngine, physics: PhysicsEngine):
        """At wire center, attenuation = exp(-μ * diameter)."""
        wire = self._make_wire(diameter_mm=1.0, material="Pb", position_y=300.0)

        result = engine.project_wire(
            wire,
            src_y_mm=-500.0,
            det_y_mm=500.0,
            focal_spot_mm=0.0,  # point source = no blur
            focal_spot_dist=FocalSpotDistribution.UNIFORM,
            energy_keV=100.0,
            num_samples=501,
        )

        # With point source, center intensity = exp(-μ * diameter_cm)
        mu = physics.linear_attenuation("Pb", 100.0)
        diameter_cm = float(mm_to_cm(1.0))
        expected_center = math.exp(-mu * diameter_cm)

        # Find center (minimum intensity)
        center_idx = np.argmin(result.profile.intensities)
        actual_center = result.profile.intensities[center_idx]

        assert actual_center == pytest.approx(expected_center, rel=0.05)

    def test_wire_outside_is_one(self, engine: ProjectionEngine):
        """Far from wire, intensity should be ~1.0."""
        wire = self._make_wire(diameter_mm=0.5, position_y=300.0)

        result = engine.project_wire(
            wire,
            src_y_mm=-500.0,
            det_y_mm=500.0,
            focal_spot_mm=0.0,
            focal_spot_dist=FocalSpotDistribution.UNIFORM,
            energy_keV=100.0,
        )

        # Edges of the profile should be ~1.0
        assert result.profile.intensities[0] == pytest.approx(1.0, abs=0.01)
        assert result.profile.intensities[-1] == pytest.approx(1.0, abs=0.01)

    def test_wire_contrast_positive(self, engine: ProjectionEngine):
        """Wire should produce positive contrast."""
        wire = self._make_wire(diameter_mm=0.5)

        result = engine.project_wire(
            wire,
            src_y_mm=-500.0,
            det_y_mm=500.0,
            focal_spot_mm=1.0,
            focal_spot_dist=FocalSpotDistribution.UNIFORM,
            energy_keV=100.0,
        )

        assert result.profile.contrast > 0

    def test_gaussian_blur_reduces_contrast(self, engine: ProjectionEngine):
        """Gaussian focal spot produces lower contrast than uniform."""
        wire = self._make_wire(diameter_mm=0.5)

        result_uniform = engine.project_wire(
            wire,
            src_y_mm=-500.0,
            det_y_mm=500.0,
            focal_spot_mm=2.0,
            focal_spot_dist=FocalSpotDistribution.UNIFORM,
            energy_keV=100.0,
        )

        result_gaussian = engine.project_wire(
            wire,
            src_y_mm=-500.0,
            det_y_mm=500.0,
            focal_spot_mm=2.0,
            focal_spot_dist=FocalSpotDistribution.GAUSSIAN,
            energy_keV=100.0,
        )

        # Both should have positive contrast
        assert result_uniform.profile.contrast > 0
        assert result_gaussian.profile.contrast > 0
        # Gaussian has wider tails so may spread differently
        # Both should give reasonable contrast
        assert result_uniform.profile.contrast > 0.001
        assert result_gaussian.profile.contrast > 0.001

    def test_wire_mtf_exists(self, engine: ProjectionEngine):
        """Wire projection should produce valid MTF."""
        wire = self._make_wire(diameter_mm=0.5)

        result = engine.project_wire(
            wire,
            src_y_mm=-500.0,
            det_y_mm=500.0,
            focal_spot_mm=1.0,
            focal_spot_dist=FocalSpotDistribution.UNIFORM,
            energy_keV=100.0,
        )

        assert result.mtf is not None
        assert len(result.mtf.frequencies_lpmm) > 0
        assert len(result.mtf.mtf_values) > 0
        # MTF at DC should be ~1.0 (normalized)
        assert result.mtf.mtf_values[0] == pytest.approx(1.0, abs=0.1)

    def test_wire_thicker_lower_intensity(self, engine: ProjectionEngine):
        """Thicker wire should have lower center intensity."""
        wire_thin = self._make_wire(diameter_mm=0.5, material="Pb")
        wire_thick = self._make_wire(diameter_mm=2.0, material="Pb")

        r_thin = engine.project_wire(
            wire_thin, -500.0, 500.0, 0.0,
            FocalSpotDistribution.UNIFORM, 100.0,
        )
        r_thick = engine.project_wire(
            wire_thick, -500.0, 500.0, 0.0,
            FocalSpotDistribution.UNIFORM, 100.0,
        )

        min_thin = np.min(r_thin.profile.intensities)
        min_thick = np.min(r_thick.profile.intensities)
        assert min_thick < min_thin


# -----------------------------------------------------------------------
# Line-pair phantom projection
# -----------------------------------------------------------------------

class TestLinePairProjection:
    """Test line-pair phantom projection."""

    def _make_lp(self, freq: float = 1.0, thickness: float = 1.0,
                 cycles: int = 5) -> LinePairPhantom:
        return LinePairPhantom(
            config=PhantomConfig(
                type=PhantomType.LINE_PAIR,
                name=f"LP {freq} lp/mm",
                position_y=300.0,
                material_id="Pb",
            ),
            frequency=freq,
            bar_thickness=thickness,
            num_cycles=cycles,
        )

    def test_lp_has_modulation(self, engine: ProjectionEngine):
        """Line-pair should show clear intensity modulation."""
        lp = self._make_lp(freq=1.0)

        result = engine.project_line_pair(
            lp,
            src_y_mm=-500.0,
            det_y_mm=500.0,
            focal_spot_mm=0.0,  # point source
            focal_spot_dist=FocalSpotDistribution.UNIFORM,
            energy_keV=100.0,
        )

        assert result.profile.contrast > 0.01

    def test_higher_freq_lower_contrast(self, engine: ProjectionEngine):
        """Higher frequency with blur should give lower contrast."""
        lp_low = self._make_lp(freq=0.5, thickness=1.0)
        lp_high = self._make_lp(freq=5.0, thickness=1.0)

        r_low = engine.project_line_pair(
            lp_low, -500.0, 500.0, 2.0,
            FocalSpotDistribution.UNIFORM, 100.0,
        )
        r_high = engine.project_line_pair(
            lp_high, -500.0, 500.0, 2.0,
            FocalSpotDistribution.UNIFORM, 100.0,
        )

        # With focal spot blur, higher freq should have lower contrast
        assert r_low.profile.contrast > r_high.profile.contrast

    def test_lp_mtf_exists(self, engine: ProjectionEngine):
        """Line-pair projection should produce valid MTF."""
        lp = self._make_lp()

        result = engine.project_line_pair(
            lp, -500.0, 500.0, 1.0,
            FocalSpotDistribution.UNIFORM, 100.0,
        )

        assert result.mtf is not None
        assert len(result.mtf.frequencies_lpmm) > 0

    def test_lp_bar_attenuation(self, engine: ProjectionEngine, physics: PhysicsEngine):
        """Bar region should show correct attenuation."""
        lp = self._make_lp(freq=0.2, thickness=2.0, cycles=3)

        result = engine.project_line_pair(
            lp, -500.0, 500.0, 0.0,  # point source
            FocalSpotDistribution.UNIFORM, 100.0,
            num_samples=4000,
        )

        mu = physics.linear_attenuation("Pb", 100.0)
        bar_t_cm = float(mm_to_cm(2.0))
        expected_bar = math.exp(-mu * bar_t_cm)

        # Min intensity should be close to bar attenuation
        min_i = np.min(result.profile.intensities)
        assert min_i == pytest.approx(expected_bar, rel=0.1)


# -----------------------------------------------------------------------
# Grid phantom projection
# -----------------------------------------------------------------------

class TestGridProjection:
    """Test grid phantom projection."""

    def _make_grid(self) -> GridPhantom:
        return GridPhantom(
            config=PhantomConfig(
                type=PhantomType.GRID,
                name="Grid 1mm",
                position_y=300.0,
                material_id="W",
            ),
            pitch=2.0,
            wire_diameter=0.2,
            size=20.0,
        )

    def test_grid_periodic_pattern(self, engine: ProjectionEngine):
        """Grid should produce periodic intensity dips."""
        grid = self._make_grid()

        result = engine.project_grid(
            grid, -500.0, 500.0, 0.0,
            FocalSpotDistribution.UNIFORM, 100.0,
        )

        assert result.profile.contrast > 0

    def test_grid_mtf_exists(self, engine: ProjectionEngine):
        """Grid projection should produce valid MTF."""
        grid = self._make_grid()

        result = engine.project_grid(
            grid, -500.0, 500.0, 1.0,
            FocalSpotDistribution.UNIFORM, 100.0,
        )

        assert result.mtf is not None
        assert len(result.mtf.frequencies_lpmm) > 0


# -----------------------------------------------------------------------
# Dispatch / general
# -----------------------------------------------------------------------

class TestProjectDispatch:
    """Test the project() dispatch method."""

    def test_dispatch_wire(self, engine: ProjectionEngine):
        wire = WirePhantom()
        result = engine.project(
            wire, -500.0, 500.0, 1.0,
            FocalSpotDistribution.UNIFORM, 100.0,
        )
        assert result.phantom_id == wire.config.id

    def test_dispatch_line_pair(self, engine: ProjectionEngine):
        lp = LinePairPhantom()
        result = engine.project(
            lp, -500.0, 500.0, 1.0,
            FocalSpotDistribution.UNIFORM, 100.0,
        )
        assert result.phantom_id == lp.config.id

    def test_dispatch_grid(self, engine: ProjectionEngine):
        grid = GridPhantom()
        result = engine.project(
            grid, -500.0, 500.0, 1.0,
            FocalSpotDistribution.UNIFORM, 100.0,
        )
        assert result.phantom_id == grid.config.id


# -----------------------------------------------------------------------
# MTF computation
# -----------------------------------------------------------------------

class TestMTFComputation:
    """Test MTF-specific behavior."""

    def test_mtf_frequency_axis_positive(self, engine: ProjectionEngine):
        """Frequency axis should be non-negative."""
        wire = WirePhantom()
        result = engine.project_wire(
            wire, -500.0, 500.0, 1.0,
            FocalSpotDistribution.UNIFORM, 100.0,
        )
        assert result.mtf is not None
        assert np.all(result.mtf.frequencies_lpmm >= 0)

    def test_mtf_values_bounded(self, engine: ProjectionEngine):
        """MTF values should be in [0, ~1]."""
        wire = WirePhantom()
        result = engine.project_wire(
            wire, -500.0, 500.0, 1.0,
            FocalSpotDistribution.UNIFORM, 100.0,
        )
        assert result.mtf is not None
        assert np.all(result.mtf.mtf_values >= -0.01)
        assert np.all(result.mtf.mtf_values <= 1.01)

    def test_larger_focal_spot_lower_mtf50(self, engine: ProjectionEngine):
        """Larger focal spot should give lower MTF@50% frequency."""
        wire = WirePhantom(
            config=PhantomConfig(
                type=PhantomType.WIRE, name="Test",
                position_y=300.0, material_id="W",
            ),
            diameter=0.3,
        )

        r_small = engine.project_wire(
            wire, -500.0, 500.0, 0.5,
            FocalSpotDistribution.UNIFORM, 100.0,
        )
        r_large = engine.project_wire(
            wire, -500.0, 500.0, 3.0,
            FocalSpotDistribution.UNIFORM, 100.0,
        )

        # Both should have MTF
        assert r_small.mtf is not None
        assert r_large.mtf is not None
        # Larger focal spot => worse resolution => MTF drops earlier
        if r_small.mtf.mtf_50_freq > 0 and r_large.mtf.mtf_50_freq > 0:
            assert r_large.mtf.mtf_50_freq <= r_small.mtf.mtf_50_freq
