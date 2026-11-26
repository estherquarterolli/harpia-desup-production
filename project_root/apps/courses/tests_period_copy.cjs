const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');

const template = fs.readFileSync(path.join(__dirname, '../../templates/courses/matrix_form.html'), 'utf8');
const start = template.indexOf('function normalizarPeriodoComponente(');
const end = template.indexOf('function preencherFormsetComCopia(', start);
const source = template.slice(start, end);

test('cópia normaliza semestres antigos e preserva valores especiais', () => {
  const context = vm.createContext({
    aplicarModoDisciplina() {},
    Option: function(text, value) { this.text = text; this.value = value; },
  });
  vm.runInContext(source, context);
  const casos = [
    ['1o periodo', '1º Período'],
    ['2º Semestre', '2º Período'],
    ['9º Período', '9º Período'],
    ['Módulo especial', 'Módulo especial'],
    ['3º Período', '3º Período'],
    ['', ''],
  ];
  for (const [periodo, esperado] of casos) {
    const select = {
      name: 'componentes-0-periodo',
      options: [{ value: '' }, { value: '3º Período' }],
      add(option) { this.options.push(option); },
      get value() { return this.selected || ''; },
      // Um select real perde a seleção quando o valor não consta das options.
      set value(value) { this.selected = this.options.some(o => o.value === value) ? value : ''; },
    };
    const row = { querySelectorAll() { return [select]; } };
    context.preencherLinhaComponente(row, { periodo });
    assert.equal(select.value, esperado);
    const count = select.options.length;
    context.preencherLinhaComponente(row, { periodo });
    assert.equal(select.options.length, count);
  }
});
