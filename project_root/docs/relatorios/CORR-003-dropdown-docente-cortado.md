# CORR-003 — Dropdown de docente cortado/some nas últimas linhas da matriz

## O que era o bug
Na tela de alocação curricular (`templates/allocations/alloc_curricular.html`), o
dropdown/autocomplete de docente era **recortado e chegava a sumir** nas linhas de
baixo da matriz.

Causa-raiz: o wrapper da tabela (linha 80) usa
`overflow-hidden overflow-x-auto`. Como o eixo X vira contexto de
scroll/clip, o CSS **força o eixo Y para `auto`** (não pode permanecer
`visible`), então qualquer elemento filho posicionado em `absolute` que
transborde para baixo é cortado. O `.ac-dropdown` (linha ~131) era
`position: absolute ... mt-1` e **sempre abria para baixo**, sem lógica de
"flip". Nas últimas linhas não havia espaço abaixo dentro do container, e o
menu era clipado (aparecendo parcial ou nenhum).

## O que mudou
Arquivo único: `templates/allocations/alloc_curricular.html` (bloco `extra_js`).
Nenhuma mudança de CSS externo, de markup do container (linha 80 preservada)
nem fora do escopo.

Estratégia (a de menor risco entre as sugeridas no checklist): **tirar o
dropdown do fluxo do container com overflow**, renderizando-o em
`position: fixed` ancorado ao input, com **flip para cima** quando não há
espaço abaixo. Assim ele não sofre clipping e o scroll horizontal da tabela
permanece intacto.

Trechos alterados (método `AutocompleteDocente`):

- `_open()` — além de exibir o dropdown, agora chama `_position()` e registra
  listeners de `scroll` (com captura, para pegar o scroll do container da
  tabela) e `resize` para reancorar enquanto o menu está aberto.
- `_close()` — remove os listeners de `scroll`/`resize` registrados no
  `_open()`.
- `_position()` (novo método) — mede `this.wrap.getBoundingClientRect()` e a
  altura real do dropdown (`offsetHeight`); compara `spaceBelow` vs.
  `spaceAbove` contra `window.innerHeight`; define
  `position: fixed`, `left`/`width` iguais aos do input e `top` abaixo
  (`rect.bottom + 4`) ou acima (`rect.top - altura - 4`, com `Math.max`)
  conforme o espaço disponível (flip). O gap de 4px replica o antigo `mt-1`.
- `_renderResults()` — ao final, chama `this._position()` para recalcular a
  ancoragem/flip depois que os resultados (carregados via fetch, portanto
  assíncronos) mudam a altura do dropdown.

As classes originais `absolute ... mt-1` continuam no template; os estilos
inline (`position: fixed`, `margin: 0`, `top/left/width`) as sobrescrevem em
runtime. `z-50` (z-index alto) foi mantido.

## Como funciona agora
- Ao focar/abrir, o dropdown é posicionado em coordenadas de viewport,
  alinhado ao input, escapando do `overflow` do container — não é mais
  recortado em nenhuma linha.
- Quando não cabe abaixo (últimas linhas, telas baixas), abre **para cima**.
- Enquanto aberto, acompanha scroll do container/página e resize da janela.
- Ao fechar (clique fora, Escape, seleção), os listeners são removidos e o
  nome atual é restaurado quando aplicável (comportamento preexistente
  mantido). O handler de "clicar fora" segue funcionando porque o dropdown
  continua sendo filho de `.ac-docente` no DOM (só a posição visual é fixed).

## Verificação
- `manage.py check` (settings `config.settings.development`):
  **"System check identified no issues (0 silenced)."**
- Sem alteração de backend/URLs/views; mudança puramente front-end.
- Teste manual sugerido: abrir uma matriz longa, rolar até as últimas linhas e
  abrir o seletor de docente — deve aparecer inteiro (abrindo para cima quando
  necessário), alinhado ao input, e fechar corretamente ao clicar fora,
  digitar/selecionar ou pressionar Escape. Validar também em tela baixa.

## Rollback
```
git checkout -- templates/allocations/alloc_curricular.html
```
(O arquivo de relatório é novo; se desejar removê-lo:
`rm docs/relatorios/CORR-003-dropdown-docente-cortado.md`.)
