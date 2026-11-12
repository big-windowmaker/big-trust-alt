# 11 — Roteiro

**Próximas versões:**

1. **Atualização do catálogo pela rede, assinada:**
   - baixar `catalog-vN.tar` + assinatura (minisign/gpg) do GitHub, conferir com a chave embutida no pacote;
   - validar o esquema e guardar em `~/.local/share/big-trust-alt/catalog/`;
   - a sobreposição e o retorno ao último válido já existem.
2. **Verificar a assinatura Authenticode** (cadeia e nome do assinante) quando houver uma ferramenta disponível (`osslsigncode`), mostrando o editor verificado.
3. **Ícone embutido do `.exe`** (RT_GROUP_ICON) quando o programa não for identificado.
4. **AppImage:** integrar ao menu (Gear Lever, se instalado) e ler o `.desktop` interno (squashfs) sem extrair.
5. **BigStore:** abrir a página do aplicativo quando houver uma interface suportada para isso.
6. **appimage-creator** como recurso avançado para empacotar programas Linux (não para os do Windows).
7. Mais idiomas (a estrutura gettext já está pronta).
8. Testes no KDE Plasma, GNOME e XFCE; teste de instalação real numa VM descartável.

**Pendências fora deste repositório:**

- **Tema BigWindowMaker/OneStepBack (GTK4):** com `GTK_THEME` definido, a libadwaita não carrega a própria folha de estilo, e o tema não estiliza as "sheets" de `AdwDialog`/`AdwAlertDialog`/`AdwAboutDialog`. Os diálogos de qualquer app libadwaita abrem sem fundo. O Big Trust Alt tem um CSS de reserva; a correção de fato vai no tema.
- **O anexo com cerca de 168 entradas** citado na especificação não foi recebido; quando chegar, entra no catálogo.
- Empacotar no repositório `big-windowmaker/packages` e incluir no perfil da ISO, se aprovado.
