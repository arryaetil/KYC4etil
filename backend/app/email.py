"""E-mailverzending via Resend (transactionele emails voor chat-uitnodigingen)."""
import httpx

from .config import get_settings


async def send_chat_invitation(to_email: str, bedrijfsnaam: str, chat_url: str) -> None:
    settings = get_settings()
    recipient = settings.email_demo_recipient or to_email
    if not recipient:
        raise ValueError("Geen ontvanger beschikbaar")

    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
      <div style="background: #1e3a5f; padding: 24px; border-radius: 8px 8px 0 0;">
        <h1 style="color: white; margin: 0; font-size: 20px;">Vestigingsregister Limburg</h1>
        <p style="color: #93c5fd; margin: 4px 0 0;">Etil Research Group &mdash; Provincie Limburg</p>
      </div>
      <div style="background: white; padding: 32px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
        <p style="color: #334155; font-size: 15px;">Beste medewerker van <strong>{bedrijfsnaam}</strong>,</p>
        <p style="color: #334155; font-size: 15px; line-height: 1.6;">
          In het kader van het Vestigingsregister van Provincie Limburg vragen wij u vriendelijk
          de personeelsgegevens van uw vestiging te controleren en eventueel aan te vullen.
        </p>
        <p style="text-align: center; margin: 32px 0;">
          <a href="{chat_url}"
             style="background: #1e40af; color: white; padding: 14px 28px;
                    border-radius: 6px; text-decoration: none; font-weight: bold;
                    font-size: 15px; display: inline-block;">
            Gegevens controleren &rarr;
          </a>
        </p>
        <p style="color: #64748b; font-size: 13px;">
          Dit duurt slechts een paar minuten. De link is 14 dagen geldig.
          Uw gegevens worden uitsluitend gebruikt voor het officiële Vestigingsregister.
        </p>
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;" />
        <p style="color: #94a3b8; font-size: 12px; margin: 0;">
          Etil Research Group &bull; Maastricht &bull; <a href="https://etil.nl" style="color: #94a3b8;">etil.nl</a>
        </p>
      </div>
    </div>
    """

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}",
                     "Content-Type": "application/json"},
            json={
                "from": settings.email_from,
                "to": [recipient],
                "subject": f"Vestigingsregister Limburg — controleer uw personeelsgegevens",
                "html": html,
            },
        )
        r.raise_for_status()
