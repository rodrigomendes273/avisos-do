# -*- coding: utf-8 -*-
import os
import re
import tempfile
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

import fitz  # PyMuPDF
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time

# ---------------- Configurações ----------------
URL_PAGINA = "https://diariooficial.prefeitura.sp.gov.br/md_epubli_controlador.php?acao=edicao_ver_ultima"
TERMO = "conservação de pavimento"

EMAIL_REMETENTE = os.environ["EMAIL_REMETENTE"]
EMAIL_SENHA = os.environ["EMAIL_SENHA"]
EMAIL_DESTINO = os.environ.get("EMAIL_DESTINO", EMAIL_REMETENTE)  # pode ser "email1@gmail.com,email2@gmail.com"
# ------------------------------------------------

try:
    # 1. Captura dinamicamente o link do PDF via Selenium
    print("Buscando link do PDF do dia com Selenium...")
    
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # roda sem abrir janela
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get(URL_PAGINA)

    # Espera alguns segundos para o JavaScript gerar o link
    time.sleep(5)

    pdf_element = driver.find_element(By.CSS_SELECTOR, 'a[data-format="pdf"]')
    PDF_URL = pdf_element.get_attribute("href")
    driver.quit()
    
    print("Link do PDF encontrado:", PDF_URL)

    # 2. Baixa o PDF
    download_path = os.path.join(tempfile.gettempdir(), "do_sp.pdf")
    print("Baixando PDF...")
    import requests
    pdf_resp = requests.get(PDF_URL)
    pdf_resp.raise_for_status()
    with open(download_path, "wb") as f:
        f.write(pdf_resp.content)
    print(f"PDF baixado com sucesso em: {download_path}")

    # 3. Lê o PDF e busca pelo termo
    print("Abrindo PDF e procurando pelo termo...")
    doc = fitz.open(download_path)
    ocorrencias = []

    termo_normalizado = TERMO.lower()
    padrao = r"\b" + r"\s+".join(map(re.escape, termo_normalizado.split())) + r"\b"

    for i, page in enumerate(doc, start=1):
        text = page.get_text()
        text_normalizado = re.sub(r'\s+', ' ', text).lower()
        for match in re.finditer(padrao, text_normalizado):
            start, end = match.start(), match.end()
            trecho = text_normalizado[max(start-50, 0):min(end+50, len(text_normalizado))]
            ocorrencias.append({"pagina": i, "trecho": trecho.strip()})

    doc.close()
    print(f"Busca concluída. {len(ocorrencias)} ocorrência(s) encontrada(s).")

    # 4. Monta a mensagem
    if ocorrencias:
        corpo = f"O termo '{TERMO}' foi encontrado nas seguintes páginas:\n\n"
        for occ in ocorrencias:
            corpo += f"- Página {occ['pagina']}: ...{occ['trecho']}...\n\n"
    else:
        corpo = f"O termo '{TERMO}' não foi encontrado no PDF do Diário Oficial."

    # 5. Prepara o e-mail
    print("Preparando e-mail...")
    msg = MIMEMultipart()
    msg["Subject"] = "Alerta Diário Oficial SP"
    msg["From"] = EMAIL_REMETENTE
    msg["To"] = EMAIL_DESTINO

    msg.attach(MIMEText(corpo, "plain"))

    # Anexa o PDF
    if os.path.exists(download_path):
        print("Anexando PDF ao e-mail...")
        with open(download_path, "rb") as f:
            part = MIMEApplication(f.read(), Name="diario.pdf")
            part['Content-Disposition'] = 'attachment; filename="diario.pdf"'
            msg.attach(part)

    # 6. Envia e-mail via Gmail
    print("Conectando ao servidor SMTP...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_REMETENTE, EMAIL_SENHA)
        print("Login realizado com sucesso.")
        server.send_message(msg)
        print("E-mail enviado com sucesso!")

    # 7. Remove PDF temporário
    if os.path.exists(download_path):
        os.remove(download_path)
        print("PDF temporário removido.")

except Exception as e:
    print(f"Ocorreu um erro: {e}")
