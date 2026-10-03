import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import pandas as pd


def verificar_e_enviar_alerta(secrets, df_atual, df_anterior, limiar=0.5):
    """
    Compara temperatura atual vs anterior para todos os lagos.
    Dispara email se algum lago subiu mais que o limiar.
    """
    if df_atual is None or df_anterior is None or df_atual.empty or df_anterior.empty:
        return False, 'Dados insuficientes'

    df = pd.merge(
        df_atual.rename(columns={'temperatura': 'temp_atual', 'data': 'data_atual'}),
        df_anterior.rename(columns={'temperatura': 'temp_ant', 'data': 'data_ant'}),
        on='lago'
    )
    df['diferenca'] = (df['temp_atual'] - df['temp_ant']).round(2)
    lagos_alerta = df[df['diferenca'] >= limiar].sort_values('diferenca', ascending=False)
    top5 = df.sort_values('temp_atual', ascending=False).head(5)

    if lagos_alerta.empty:
        return False, 'Nenhum lago acima do limiar'

    enviado = _enviar_email(secrets, lagos_alerta, top5, limiar)
    return enviado, f'{len(lagos_alerta)} lago(s) em alerta'


def _enviar_email(secrets, lagos_alerta, top5, limiar):
    remetente    = secrets['EMAIL_REMETENTE']
    senha        = secrets['EMAIL_SENHA_APP']
    destinatario = secrets['EMAIL_DESTINATARIO']
    data_hoje    = datetime.utcnow().strftime('%d/%m/%Y %H:%M UTC')

    linhas_alerta = ''
    for _, row in lagos_alerta.iterrows():
        cor = '#A85448' if row['diferenca'] >= 1.0 else '#C18C5D'
        linhas_alerta += (
            '<tr>'
            f'<td style="padding:8px;border-bottom:1px solid #F0EBE5">{row["lago"]}</td>'
            f'<td style="padding:8px;border-bottom:1px solid #F0EBE5;text-align:center">'
            f'{row["temp_ant"]:.1f}C<br>'
            f'<small style="color:#78786C">{row.get("data_ant","")}</small></td>'
            f'<td style="padding:8px;border-bottom:1px solid #F0EBE5;text-align:center">'
            f'{row["temp_atual"]:.1f}C<br>'
            f'<small style="color:#78786C">{row.get("data_atual","")}</small></td>'
            f'<td style="padding:8px;border-bottom:1px solid #F0EBE5;'
            f'text-align:center;color:{cor};font-weight:bold">'
            f'+{row["diferenca"]:.2f}C</td>'
            '</tr>'
        )

    linhas_top5 = ''
    medalhas = ['1o', '2o', '3o', '4o', '5o']
    for i, (_, row) in enumerate(top5.iterrows()):
        linhas_top5 += (
            '<tr>'
            f'<td style="padding:8px;border-bottom:1px solid #F0EBE5">'
            f'{medalhas[i]} {row["lago"]}</td>'
            f'<td style="padding:8px;border-bottom:1px solid #F0EBE5;'
            f'text-align:center;font-weight:bold;color:#A85448">'
            f'{row["temp_atual"]:.1f}C</td>'
            f'<td style="padding:8px;border-bottom:1px solid #F0EBE5;'
            f'text-align:center;color:#78786C">{row.get("data_atual","")}</td>'
            '</tr>'
        )

    html = (
        '<html><body style="font-family:Arial,sans-serif;background:#FDFCF8;padding:20px">'
        '<div style="max-width:600px;margin:0 auto;background:white;'
        'border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(93,112,82,0.15)">'
        '<div style="background:#5D7052;padding:24px;text-align:center">'
        '<h1 style="color:white;margin:0;font-size:20px">'
        'Alerta de Temperatura - Lagos Amazonicos</h1>'
        f'<p style="color:rgba(255,255,255,0.8);margin:8px 0 0">{data_hoje}</p>'
        '</div>'
        '<div style="background:#FFF3E0;padding:16px 24px;border-left:4px solid #C18C5D">'
        f'<p style="margin:0;color:#2C2C24"><strong>{len(lagos_alerta)} lago(s)</strong> '
        f'apresentaram aumento superior a <strong>{limiar}C</strong> '
        'em relacao ao ultimo registro.</p>'
        '</div>'
        '<div style="padding:24px">'
        '<h2 style="color:#5D7052;font-size:16px;margin:0 0 12px">'
        'Lagos com aumento significativo</h2>'
        '<table style="width:100%;border-collapse:collapse;font-size:14px">'
        '<thead><tr style="background:#F0EBE5">'
        '<th style="padding:10px;text-align:left">Lago</th>'
        '<th style="padding:10px;text-align:center">Temp anterior</th>'
        '<th style="padding:10px;text-align:center">Temp atual</th>'
        '<th style="padding:10px;text-align:center">Variacao</th>'
        '</tr></thead>'
        f'<tbody>{linhas_alerta}</tbody></table></div>'
        '<div style="padding:0 24px 24px">'
        '<h2 style="color:#5D7052;font-size:16px;margin:0 0 12px">'
        'Top 5 mais quentes agora</h2>'
        '<table style="width:100%;border-collapse:collapse;font-size:14px">'
        '<thead><tr style="background:#F0EBE5">'
        '<th style="padding:10px;text-align:left">Lago</th>'
        '<th style="padding:10px;text-align:center">Temperatura</th>'
        '<th style="padding:10px;text-align:center">Data</th>'
        '</tr></thead>'
        f'<tbody>{linhas_top5}</tbody></table></div>'
        '<div style="background:#F0EBE5;padding:16px 24px;text-align:center">'
        '<p style="margin:0;font-size:12px;color:#78786C">'
        'Dashboard WebGIS Botos - WWF Brasil<br>'
        '<a href="https://monitoramentobotos.streamlit.app/Analises_e_Estatisticas"'
        ' style="color:#5D7052">Acessar o dashboard</a></p>'
        '</div></div></body></html>'
    )

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'Alerta Temperatura Botos - {len(lagos_alerta)} lago(s) em alta'
        msg['From']    = remetente
        msg['To']      = destinatario
        msg.attach(MIMEText(html, 'html'))
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(remetente, senha)
            smtp.sendmail(remetente, destinatario, msg.as_string())
        print(f'Email enviado para {destinatario}!')
        return True
    except Exception as e:
        print(f'Erro ao enviar email: {e}')
        return False
