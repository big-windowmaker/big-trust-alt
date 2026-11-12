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

- O `.desktop` declara todos os tipos analisados: os do Windows (`application/x-msdownload`, `x-ms-dos-executable`, `vnd.microsoft.portable-executable`, `x-msi`, `msix`, `appx`, `x-bat`) e `vnd.debian.binary-package`, `x-deb`, `x-rpm`, `vnd.appimage`, `x-executable`, `x-shellscript`, `java-archive`, `vnd.flatpak.ref`, `vnd.flatpak`. Assim ele aparece em "Abrir com" em qualquer desktop.
- **Nas sessões Big WindowMaker o Big Trust Alt abre primeiro.** Isso é decidido pelo big-wm em `/etc/xdg/{windowmaker,wlmaker}-mimeapps.list`, que o XDG lê antes do `/etc/xdg/mimeapps.list` da BigLinux (o qual manda `.deb` para o big-pkg-installer, `.rpm` para o rpmtoarch e AppImage/scripts para o big-executable). Esses programas ficam atrás na lista: sem o Big Trust Alt, o XDG abre o próximo.
- Em outros desktops o padrão não muda ao instalar. A opção "Abrir programas e pacotes baixados com o Big Trust Alt" das Preferências (ou `big-trust-alt --associate`) grava o padrão no `~/.config/mimeapps.list` e guarda os anteriores; desligar (`--dissociate`) restaura tudo.
- A escolha do usuário (`~/.config/mimeapps.list`) vale mais que a da sessão.
- Dentro do Big Trust Alt, "Converter e instalar" chama o `big-pkg-installer-gui` diretamente, e executar um AppImage ou script chama o próprio arquivo: não há volta para o Big Trust Alt.
