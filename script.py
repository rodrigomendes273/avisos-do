import requests
import fitz  # PyMuPDF
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import re
import os

URL = "https://diariooficial.prefeitura.sp.gov.br/md_epubli_controlador.php?acao=diario_aberto&formato=A"

# ---------------- Buscar link do PDF ----------------
try:
    response = requests.get(URL, timeout=15)
    response.raise_for_status()
    html = response.text

    pattern = r'<a\s+target="_blank"\s+data-format="pdf"\s+href="([^"]+)"'
    match = re.search(pattern, html)

    if match:
        PDF_URL = match.group(1)

        # Corrige link relativo
        if PDF_URL.startswith("/"):
            PDF_URL = "https://diariooficial.prefeitura.sp.gov.br" + PDF_URL
    else:
        raise Exception("Não foi possível encontrar o link do PDF.")

except Exception as e:
    raise SystemExit(f"Erro ao buscar o PDF: {e}")

# ---------------- Configurações ----------------
DOWNLOAD_PDF_PATH = "/tmp/do_sp.pdf"
TERMO = "MRS SEGURANÇA"

EMAIL_REMETENTE = os.environ["EMAIL_REMETENTE"]
EMAIL_SENHA = os.environ["EMAIL_SENHA"]
EMAIL_DESTINO = os.environ.get("EMAIL_DESTINO", EMAIL_REMETENTE)
# ------------------------------------------------

try:
    # 1. Baixa o PDF
    pdf_resp = requests.get(PDF_URL)
    with open(DOWNLOAD_PDF_PATH, "wb") as f:
        f.write(pdf_resp.content)

    # 2. Lê o PDF
    doc = fitz.open(DOWNLOAD_PDF_PATH)
    ocorrencias = []

    termo_normalizado = TERMO.lower()
    padrao = re.sub(r'\s+', r'\\s+', termo_normalizado)

    for i, page in enumerate(doc, start=1):
        text = page.get_text()
        text_normalizado = re.sub(r'\s+', ' ', text).lower()

        for match in re.finditer(padrao, text_normalizado):
            start, end = match.start(), match.end()
            trecho = text_normalizado[max(start-30, 0):min(end+30, len(text_normalizado))]
            ocorrencias.append({"pagina": i, "trecho": trecho.strip()})

    doc.close()

    # 3. Corpo do e-mail
    if ocorrencias:
        corpo = f"O termo '{TERMO}' foi encontrado:\n\n"
        for occ in ocorrencias:
            corpo += f"- Página {occ['pagina']}: ...{occ['trecho']}...\n\n"
    else:
        corpo = f"O termo '{TERMO}' não foi encontrado no PDF do Diário Oficial."

    # 4. Monta o e-mail
    msg = MIMEMultipart()
    msg["Subject"] = "Alerta Diário Oficial SP"
    msg["From"] = EMAIL_REMETENTE
    msg["To"] = EMAIL_DESTINO
    msg.attach(MIMEText(corpo, "plain"))

    # Anexo
    if os.path.exists(DOWNLOAD_PDF_PATH):
        with open(DOWNLOAD_PDF_PATH, "rb") as f:
            part = MIMEApplication(f.read(), Name="diario.pdf")
            part['Content-Disposition'] = 'attachment; filename="diario.pdf"'
            msg.attach(part)

    # 5. Envio via Gmail
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_REMETENTE, EMAIL_SENHA)
        server.send_message(msg)

except Exception as e:
    raise SystemExit(f"Erro no processamento: {e}")
