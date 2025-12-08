import requests
import fitz  # PyMuPDF
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import re
import os

# ---------------- Busca automática do link PDF ----------------

URL_PAGINA = "https://diariooficial.prefeitura.sp.gov.br/md_epubli_controlador.php?acao=edicao_ver_ultima"

print("Buscando página para extrair link do PDF...")

resp = requests.get(URL_PAGINA)
html = resp.text

match = re.search(r'<a[^>]*data-format="pdf"[^>]*href="(.*?)"', html)

if match:
    PDF_URL = match.group(1)
    print(f"Link do PDF encontrado:\n{PDF_URL}")
else:
    raise Exception("Não foi possível encontrar o link do PDF.")

# ----------------------------------------------------------------

DOWNLOAD_PDF_PATH = "/tmp/do_sp.pdf"  # caminho temporário no GitHub Actions
TERMO = "conservação de pavimento"

EMAIL_REMETENTE = os.environ["EMAIL_REMETENTE"]
EMAIL_SENHA = os.environ["EMAIL_SENHA"]
EMAIL_DESTINO = os.environ.get("EMAIL_DESTINO", EMAIL_REMETENTE)

try:
    # 1. Baixa o PDF
    print("Baixando PDF...")
    pdf_resp = requests.get(PDF_URL)
    with open(DOWNLOAD_PDF_PATH, "wb") as f:
        f.write(pdf_resp.content)
    print(f"PDF baixado com sucesso em: {DOWNLOAD_PDF_PATH}")

    # 2. Lê o PDF e busca pelo termo
    print("Abrindo PDF e procurando pelo termo...")
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
    print(f"Busca concluída. {len(ocorrencias)} ocorrência(s) encontrada(s).")

    # 3. Monta a mensagem
    if ocorrencias:
        corpo = f"O termo '{TERMO}' foi encontrado nas seguintes páginas:\n\n"
        for occ in ocorrencias:
            corpo += f"- Página {occ['pagina']}: ...{occ['trecho']}...\n\n"
    else:
        corpo = f"O termo '{TERMO}' NÃO foi encontrado no PDF do Diário Oficial."

    # 4. Prepara o e-mail
    print("Preparando e-mail...")
    msg = MIMEMultipart()
    msg["Subject"] = "Alerta Diário Oficial SP"
    msg["From"] = EMAIL_REMETENTE
    msg["To"] = EMAIL_DESTINO

    msg.attach(MIMEText(corpo, "plain"))

    # Anexo PDF
    if os.path.exists(DOWNLOAD_PDF_PATH):
        print("Anexando PDF ao e-mail...")
        with open(DOWNLOAD_PDF_PATH, "rb") as f:
            part = MIMEApplication(f.read(), Name="diario.pdf")
            part['Content-Disposition'] = 'attachment; filename="diario.pdf"'
            msg.attach(part)

    # 5. Envia e-mail via Gmail
    print("Conectando ao servidor SMTP...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_REMETENTE, EMAIL_SENHA)
        print("Login realizado com sucesso.")
        server.send_message(msg)
        print("E-mail enviado com sucesso!")

except Exception as e:
    print(f"Ocorreu um erro: {e}")
