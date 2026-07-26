class LicenseException(Exception):
    """Base exception for all licensing errors."""


class InvalidLicenseException(LicenseException):
    """Raised when the uploaded license format is invalid."""


class InvalidSignatureException(LicenseException):
    """Raised when RSA signature verification fails."""


class ExpiredLicenseException(LicenseException):
    """Raised when the license has expired."""


class DomainMismatchException(LicenseException):
    """Raised when the current domain doesn't match the licensed domain."""


class NoActiveLicenseException(LicenseException):
    """Raised when no active license exists."""