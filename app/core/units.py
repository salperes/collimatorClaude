"""Unit conversion module — single conversion point between UI and Core layers.

CRITICAL: All unit conversions MUST go through this module.

Internal (core) units:
    Length   : cm
    Energy   : keV
    Density  : g/cm³
    μ/ρ      : cm²/g
    μ        : cm⁻¹
    σ        : cm²
    Thickness: mfp (dimensionless)
    Angle    : radian

UI units:
    Length   : mm
    Energy   : keV or MeV
    Angle    : degree
"""

import math
from typing import NewType

# Type aliases — zero runtime cost, visible in IDE for unit-error detection
Cm = NewType('Cm', float)
Mm = NewType('Mm', float)
KeV = NewType('KeV', float)
Mfp = NewType('Mfp', float)
Radian = NewType('Radian', float)


# ---------------------------------------------------------------------------
# Length conversions
# ---------------------------------------------------------------------------

def mm_to_cm(mm: float) -> Cm:
    """UI (mm) → Core (cm)."""
    return Cm(mm * 0.1)


def cm_to_mm(cm: float) -> Mm:
    """Core (cm) → UI (mm)."""
    return Mm(cm * 10.0)


# ---------------------------------------------------------------------------
# Energy conversions
# ---------------------------------------------------------------------------

def MeV_to_keV(mev: float) -> KeV:
    """MeV → keV."""
    return KeV(mev * 1000.0)


def keV_to_MeV(kev: float) -> float:
    """keV → MeV."""
    return kev / 1000.0


# ---------------------------------------------------------------------------
# Angle conversions
# ---------------------------------------------------------------------------

def deg_to_rad(deg: float) -> Radian:
    """Degree → Radian."""
    return Radian(deg * (math.pi / 180.0))


def rad_to_deg(rad: float) -> float:
    """Radian → Degree."""
    return rad * (180.0 / math.pi)


# ---------------------------------------------------------------------------
# Optical thickness conversions
# ---------------------------------------------------------------------------

def thickness_to_mfp(thickness_cm: float, mu_per_cm: float) -> Mfp:
    """Physical thickness [cm] × linear attenuation [cm⁻¹] → optical thickness [mfp].

    Args:
        thickness_cm: Material thickness [cm].
        mu_per_cm: Linear attenuation coefficient [cm⁻¹].

    Returns:
        Optical thickness [mfp, dimensionless].
    """
    return Mfp(mu_per_cm * thickness_cm)


def mfp_to_thickness(mfp: float, mu_per_cm: float) -> Cm:
    """Optical thickness [mfp] → physical thickness [cm].

    Args:
        mfp: Optical thickness [mfp, dimensionless].
        mu_per_cm: Linear attenuation coefficient [cm⁻¹].

    Returns:
        Physical thickness [cm].
    """
    return Cm(mfp / mu_per_cm)


# ---------------------------------------------------------------------------
# Attenuation conversions
# ---------------------------------------------------------------------------

def transmission_to_dB(transmission: float) -> float:
    """Transmission ratio (0–1) → attenuation in dB.

    Args:
        transmission: Transmission ratio [dimensionless, 0–1].

    Returns:
        Attenuation [dB, positive value].
    """
    return -10.0 * math.log10(max(transmission, 1e-30))


def dB_to_transmission(dB: float) -> float:
    """Attenuation in dB → transmission ratio.

    Args:
        dB: Attenuation [dB, positive value].

    Returns:
        Transmission ratio [dimensionless, 0–1].
    """
    return 10.0 ** (-dB / 10.0)


# ---------------------------------------------------------------------------
# Dose rate conversions
# ---------------------------------------------------------------------------

def Gy_h_to_µSv_h(gy_h: float) -> float:
    """Gy/h → µSv/h (photon radiation weighting factor wR = 1)."""
    return gy_h * 1_000_000.0


def µSv_h_to_Gy_h(usv_h: float) -> float:
    """µSv/h → Gy/h."""
    return usv_h * 1e-6


def Gy_min_to_Gy_h(gy_min: float) -> float:
    """Gy/min → Gy/h."""
    return gy_min * 60.0
