"""Portal de empleo DEMO (entorno controlado, §6.2 del reto).

Simula el formulario de postulación de una empresa: valida campos obligatorios y
devuelve un comprobante. El Agente de Postulación "llena" este formulario.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

REQUIRED_FIELDS = ["vacancy_id", "full_name", "document_type", "document_id", "email", "phone", "city",
                   "salary_expectation_cop", "cover_letter"]


class PortalRejected(ValueError):
    pass


def submit_application(form: dict) -> dict:
    missing = [f for f in REQUIRED_FIELDS if not form.get(f)]
    if missing:
        raise PortalRejected(f"Faltan campos obligatorios: {', '.join(missing)}")
    body = json.dumps(form, ensure_ascii=False, sort_keys=True)
    return {
        "receipt_id": "RCPT-" + uuid.uuid4().hex[:10].upper(),
        "received_at": datetime.now(UTC).isoformat(),
        "payload_sha256": hashlib.sha256(body.encode()).hexdigest(),
        "portal": "demo-portal.local",
        "message": "Postulación recibida correctamente",
    }
