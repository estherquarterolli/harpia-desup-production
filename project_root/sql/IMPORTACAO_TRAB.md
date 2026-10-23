# Atualização de professores a partir do PDF TRAB

O PDF fornecido contém 2.999 linhas e 2.869 IDs funcionais distintos. Os arquivos SQL gerados a partir dele ficam em `sql/local/`, ignorado pelo Git porque contêm dados pessoais.

## Ordem de execução

1. Faça um backup do banco PostgreSQL/Supabase.
2. Execute `sql/local/conferir_professores_trab.sql`. Ele mostra os cadastros encontrados, vínculos do PDF, divergências de matrícula, IDs ambíguos e cargos sem correspondência. Termina em `ROLLBACK` e não altera cadastros.
3. Revise os relatórios. No editor SQL do Supabase, execute **todo o conteúdo** de `sql/local/supabase_1_carregar_professores_trab.sql`. Ele cria as quatro colunas se necessário e carrega as 2.999 linhas em um esquema privado.
4. Execute **todo o conteúdo** de `sql/local/supabase_2_atualizar_professores_trab.sql`. Ele identifica os cadastros, atualiza os dados e remove o esquema de importação ao concluir.

O arquivo `sql/local/supabase_importar_professores_trab.sql` contém as duas etapas em sequência para execução integral. Não execute apenas o trecho selecionado no editor: a etapa de atualização depende de a carga inteira ter sido concluída. A tabela de origem agora persiste entre execuções do SQL Editor, evitando que desapareça entre comandos.

A migração Django `professors.0013` pode ser aplicada depois desse SQL: ela reconhece as colunas já criadas. Se a migração já tiver sido aplicada, o SQL do Supabase também funciona.

## Regras da atualização

- Só altera professores já cadastrados. Usa o ID funcional e, quando há mais de uma linha no PDF para o mesmo ID, exige matrícula exatamente igual à cadastrada.
- Matrícula divergente não é sobrescrita. Matrícula vazia no cadastro só é preenchida quando a do PDF estiver livre.
- Atualiza nome, vínculo empregatício, setor de origem e cargo de origem. Também atualiza disciplina/área de atuação quando o PDF a informa.
- `CONCURSO PUBLICO` do PDF é gravado como `EFETIVO`.
- O cargo operacional (`tipo_contrato_id`) só muda se existir exatamente um tipo de contrato com o mesmo nome. O cargo original do PDF fica salvo em `cargo_origem` mesmo sem essa correspondência. A troca do tipo de contrato pode alterar os limites de carga horária.
- O nome é gravado em formato de título e o ajuste manual `desup_nome` é limpo para que o nome do PDF apareça na interface.
- O setor é armazenado como texto em `setor_origem`; os vínculos com unidades existentes não são inferidos do texto do PDF.

O número de professores cadastrados que podem ser atualizados depende do conteúdo do banco real e aparece no relatório de conferência. Nenhuma atualização do banco foi executada na preparação destes arquivos.
