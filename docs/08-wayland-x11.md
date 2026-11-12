# 08 — Wayland e X11

Testado em laboratório isolado (HOME descartável, barramento próprio, systemctl/loginctl bloqueados), nunca na tela real:

| Sessão | Ambiente | Resultado |
|---|---|---|
| X11 | Xvfb 1280×900 + Window Maker com a configuração do Big WindowMaker (`big-wm-firstrun x11`) | **verificado**: moldura do Window Maker (sem CSD), páginas, diálogo de confirmação, temas BigWindowMaker, OneStepBack-Dark e Adwaita escuro |
| Wayland | wlmaker 35 aninhado (`WLR_BACKENDS=x11`), `GDK_BACKEND=wayland` | **verificado**: moldura do wlmaker, resultado do Spotify, Flathub listado depois da correção do cache |
| Arrastar e soltar | `Gtk.DropTarget(Gdk.FileList)` | implementado; **não verificado** com um gerenciador de arquivos real arrastando |
| Thunar / gerenciador de arquivos | associação MIME (`.desktop`) | ver docs/09 |
| Polkit | delegado ao Pamac e ao Flatpak | **não verificado** no laboratório (sem agente Polkit de propósito, para não mexer no sistema real) |

Sem dependência de KDE, GNOME ou de um compositor: só GTK4, XDG e `Gio`.

**Associação de arquivos:**

- O `.desktop` declara apenas os tipos do Windows (`application/x-msdownload`, `x-ms-dos-executable`, `vnd.microsoft.portable-executable`, `x-msi`, `msix`, `appx`, `x-bat`).
- Instalar o pacote **não grava** nenhum padrão.
- Nas Preferências, "Abrir programas do Windows com o Big Trust Alt":
  - grava o padrão no `~/.config/mimeapps.list` e guarda os anteriores;
  - acrescenta o app em "Abrir com" para `.deb`, `.rpm`, AppImage, `.jar`, `.flatpakref` e scripts, sem mudar o padrão desses tipos;
  - desligar a opção restaura tudo (`big-trust-alt --dissociate`).
- O `big-pkg-installer` continua o padrão de `.deb/.rpm`. O `big-executable` continua com `x-executable/x-shellscript`.
