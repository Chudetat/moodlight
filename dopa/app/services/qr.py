"""QR code generation service."""
import io
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
from ..config import get_settings

settings = get_settings()


class QRService:
    """Service for generating QR codes for event opt-in pages."""

    def generate_opt_in_qr(self, opt_in_code: str) -> bytes:
        """Generate a QR code that links to the event opt-in page."""
        opt_in_url = f"{settings.app_url}/opt-in/{opt_in_code}"
        return self._generate_qr(opt_in_url)

    def _generate_qr(self, data: str) -> bytes:
        """Generate a styled QR code as PNG bytes."""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)

        img = qr.make_image(
            image_factory=StyledPilImage,
            module_drawer=RoundedModuleDrawer(),
        )

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()

    def get_opt_in_url(self, opt_in_code: str) -> str:
        """Get the full opt-in URL for an event."""
        return f"{settings.app_url}/opt-in/{opt_in_code}"


def get_qr_service() -> QRService:
    """Dependency for getting QR service instance."""
    return QRService()
