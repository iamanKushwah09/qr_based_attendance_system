import qrcode
import uuid
import os


def generate_uuid_qr(student_id: str):
    unique_id = str(uuid.uuid4())

    # project root path (attendance system/)
    base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    folder = os.path.join(base_path, "QR", "qrcodes")

    # ensure folder exists
    os.makedirs(folder, exist_ok=True)

    file_path = os.path.join(folder, f"{student_id}.png")

    img = qrcode.make(unique_id)
    img.save(file_path)

    return unique_id, file_path
