# 07 — UX/UI

**Fluxo:** abrir arquivo (associação MIME, arrastar, escolher) → análise em segundo plano (spinner, cancelável) → resultado:

1. **Cabeçalho:**
   - ícone do programa (do tema ou do Flatpak) e nome do arquivo (caracteres invisíveis à vista);
   - título: "Encontramos uma maneira melhor de usar este programa no Linux.";
   - "Instalador do Windows (NSIS) identificado como Notepad++";
   - selos de nível, plataforma e arquitetura;
   - aviso de que identificar não garante a origem.
2. **Cartão vermelho**, só com um aviso grave (extensão falsa, nome enganoso).
3. **"Recomendado para o BigLinux":**
   - um cartão com a opção e o porquê ("Vem dos repositórios do sistema: testado com o BigLinux…");
   - selo da relação (Mesmo programa · Alternativa funcional · Sucessor · Versão web · Lançador de jogos);
   - o botão principal recebe o foco.
4. **Outras opções**: linhas com ícone, origem e relação; as indisponíveis aparecem desativadas com o motivo.
5. **Arquivo original** (nunca escondido, nunca padrão): ver o conteúdo do script, executar com o Wine/Bottles/Java ou executar o próprio arquivo. Exige o diálogo de confirmação, com "Cancelar" como padrão, a caixa "marcar como executável" e o SHA-256.
6. **Detalhes técnicos** (expansível): tipo, tamanho, SHA-256 (copiar), origem, metadados, candidatos com pontuação e o comando de cada opção.
7. "Analisar outro arquivo" · "Informar identificação errada".

**Outras páginas:**

- **Procurar alternativa:** sem arquivo, por exemplo "Photoshop" → GIMP e Krita, com o aviso de que não são versões do Photoshop.
- **Histórico.**
- **Preferências:** preferir Flatpak, mostrar o AUR, histórico, associação de arquivos.
- **Sobre.**

**Acessibilidade:**

- tudo pelo teclado (Ctrl+O, Ctrl+F, Ctrl+H, Ctrl+vírgula, Ctrl+W);
- os botões das linhas têm rótulo acessível com o nome da opção;
- ícones decorativos com papel de apresentação;
- texto quebra em telas de 360 px (`Adw.Clamp`).

**Tema:**

- segue claro/escuro; testado com Adwaita, BigWindowMaker (OneStepBack) e OneStepBack-Dark;
- as cores dos selos misturam a cor de destaque com a cor do texto e ficam legíveis mesmo quando o tema mantém as cores escuras no modo escuro.

**Ícone:** escudo (confiança) com uma bifurcação (escolha) e o selo verde (verificado), em SVG próprio. A versão simbólica vai junto.

**Tema do Big WindowMaker:**

- Com `GTK_THEME=BigWindowMaker`, a libadwaita não carrega a folha de estilo dela, e o tema não estiliza as "sheets" dos diálogos (`AdwDialog`): eles abriam sem fundo.
- O app traz um CSS de reserva com as variáveis do próprio tema.
- **A correção de fato pertence ao tema** (onestepback-gtk-theme / big-wm): pendência registrada no roteiro.
