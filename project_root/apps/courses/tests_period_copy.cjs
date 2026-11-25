const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');

const template = fs.readFileSync(path.join(__dirname, '../../templates/courses/matrix_form.html'), 'utf8');
const start = template.indexOf('function preencherLinhaComponente(');
const end = template.indexOf('function preencherFormsetComCopia(', start);
const source = template.slice(start, end);

test('cópia seleciona períodos legados sem depender das opções da linha original', () => {
  const context = vm.createContext({
    aplicarModoDisciplina() {},
    Option: function(text, value) { this.text = text; this.value = value; },
  });
  vm.runInContext(source, context);
  for (const periodo of ['1o periodo', '2º Semestre', '9º Período', 'Módulo especial', '3º Período', '']) {
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
    assert.equal(select.value, periodo);
    const count = select.options.length;
    context.preencherLinhaComponente(row, { periodo });
    assert.equal(select.options.length, count);
  }
});
