const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');

const template = fs.readFileSync(path.join(__dirname, '../../templates/allocations/alloc_curricular.html'), 'utf8');
const controller = template.slice(template.indexOf('class AutocompleteDocente {'), template.indexOf('const MAX_TURMAS = 20;'));
const pending = template.slice(template.indexOf('function rowPending('), template.indexOf('function countPending('));

// DOM mínimo para executar o controlador real, incluindo a restauração de falhas.
class Element {
  constructor(className = '') {
    this.className = className;
    this.children = [];
    this.dataset = {};
    this.style = {};
    this.value = '';
    this.events = {};
    this.classList = {
      contains: name => this.className.split(/\s+/).includes(name),
      add: name => { if (!this.classList.contains(name)) this.className += ` ${name}`; },
      remove: name => { this.className = this.className.split(/\s+/).filter(item => item !== name).join(' '); },
    };
  }
  appendChild(child) { child.parent = this; this.children.push(child); return child; }
  insertBefore(child, reference) {
    child.parent = this;
    this.children.splice(this.children.indexOf(reference), 0, child);
  }
  after(child) { this.parent.insertBefore(child, this.parent.children[this.parent.children.indexOf(this) + 1]); }
  remove() { this.parent.children.splice(this.parent.children.indexOf(this), 1); }
  removeAttribute(name) { delete this[name]; }
  addEventListener(name, callback) { this.events[name] = callback; }
  matches(selector) { return this.classList.contains(selector.split('.').at(-1)); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  querySelectorAll(selector) {
    if (selector.includes(' ') && !selector.startsWith(':scope > ')) return [];
    const direct = selector.startsWith(':scope > ');
    const result = [];
    for (const child of this.children) {
      if (child.matches(selector)) result.push(child);
      if (!direct) result.push(...child.querySelectorAll(selector));
    }
    return result;
  }
  closest(selector) { return this.matches(selector) ? this : this.parent?.closest(selector) || null; }
}

function setup({ currentId = 'NAO_INFORMADO', linhaId = '', fail = false } = {}) {
  const calls = [];
  const context = vm.createContext({
    document: { createElement: () => new Element() },
    window: { addEventListener() {}, removeEventListener() {} },
    debounce: fn => fn,
    DEBOUNCE_MS: 250,
    getCSRFToken: () => 'test-csrf',
    UNIDADE_ID: '1',
    URLSearchParams,
    showAllocToast() {}, markAllocationChanged() {}, refreshAllocSummary() {},
    fetch: async (url, options) => {
      calls.push({ url, options });
      if (fail) throw new Error('Network unavailable');
      return { status: 200, ok: true, json: async () => ({ ok: true, linha_id: 11 }) };
    },
  });
  vm.runInContext(`${pending}\n${controller}\nthis.Controller = AutocompleteDocente;`, context);
  const slots = new Element('ac-slots');
  slots.dataset.alocarUrl = '/componente/1/alocar/';
  const slot = slots.appendChild(new Element('ac-slot'));
  const root = slot.appendChild(new Element('ac-docente'));
  root.dataset = { currentId, currentNome: '', linhaId };
  const wrap = root.appendChild(new Element('ac-input-wrap border-slate-300 bg-slate-50'));
  wrap.appendChild(new Element('ph ph-chalkboard-teacher text-slate-400'));
  const input = wrap.appendChild(new Element('ac-input text-slate-400'));
  input.placeholder = 'Não informado';
  wrap.appendChild(new Element('ac-caret'));
  const dropdown = root.appendChild(new Element('ac-dropdown hidden'));
  dropdown.appendChild(new Element('ac-results'));
  const ac = new context.Controller(root);
  ac._position = () => {};
  return { ac, calls, root, wrap, input, context, slots };
}

test('abrir, buscar e fechar campo inicial não declara carência', () => {
  const { ac, calls, root, wrap, input } = setup();
  ac._doSearch = () => {};
  ac.input.select = () => {};
  input.events.focus();
  input.value = 'Busca não selecionada';
  ac._close();
  assert.equal(calls.length, 0);
  assert.equal(root.dataset.currentId, 'NAO_INFORMADO');
  assert.equal(input.value, '');
  assert.equal(input.placeholder, 'Não informado');
  assert.match(wrap.className, /bg-slate-50/);
});

test('escolher Sem professor salva carência vermelha, inclusive o ícone inicial', async () => {
  const { ac, calls, root, wrap, input } = setup();
  await ac._selectValue('SEM_PROFESSOR', 'Sem professor (carência)');
  assert.equal(calls.length, 1);
  assert.equal(new URLSearchParams(calls[0].options.body).get('docente_id'), 'SEM_PROFESSOR');
  assert.equal(root.dataset.linhaId, '11');
  assert.equal(root.dataset.currentId, 'SEM_PROFESSOR');
  assert.equal(input.placeholder, 'Sem professor');
  assert.match(input.className, /ac-text-carencia/);
  assert.match(wrap.className, /ac-state-carencia/);
  assert.match(wrap.querySelector(':scope > i.ph-chalkboard-teacher').className, /ac-carencia-icon/);
  await ac._selectValue('SEM_PROFESSOR', 'Sem professor (carência)');
  assert.equal(calls.length, 1);
});

test('falha no primeiro salvamento restaura Não informado cinza e sem docente fictício', async () => {
  const { ac, root, wrap, input } = setup({ fail: true });
  await ac._selectValue('SEM_PROFESSOR', 'Sem professor (carência)');
  assert.equal(root.dataset.currentId, 'NAO_INFORMADO');
  assert.equal(root.dataset.linhaId, '');
  assert.equal(input.placeholder, 'Não informado');
  assert.match(wrap.className, /bg-slate-50/);
  assert.doesNotMatch(input.className, /ac-text-carencia|text-emerald/);
  assert.match(wrap.querySelector(':scope > i.ph-chalkboard-teacher').className, /text-slate-400/);
  assert.equal(wrap.querySelector('.ac-clear'), null);
});

test('falha ao trocar carência salva por docente restaura carência vermelha', async () => {
  const { ac, root, wrap, input } = setup({ currentId: 'SEM_PROFESSOR', linhaId: '7', fail: true });
  await ac._selectValue('42', 'Docente');
  assert.equal(root.dataset.currentId, 'SEM_PROFESSOR');
  assert.equal(root.dataset.linhaId, '7');
  assert.equal(input.placeholder, 'Sem professor');
  assert.match(wrap.className, /ac-state-carencia/);
  assert.equal(wrap.querySelector('.ac-clear'), null);
});

test('Não informado e carência impedem aprovação; docente e não oferta são distintos', () => {
  const { context } = setup();
  const tr = ids => ({ querySelectorAll: () => ids.map(currentId => ({ dataset: { currentId } })) });
  for (const ids of [['NAO_INFORMADO'], ['SEM_PROFESSOR'], ['42', 'NAO_INFORMADO'], ['42', 'SEM_PROFESSOR']]) {
    assert.equal(context.rowPending(tr(ids)), true, ids.join(', '));
  }
  assert.equal(context.rowPending(tr(['42'])), false);
  assert.equal(context.rowPending(tr(['NAO_OFERECIDA'])), false);
});

test('resumo de Alocação Salva conta Não informado e carência como pendentes', () => {
  const start = template.indexOf('window.openAllocSavedModal = function () {');
  const source = template.slice(start, template.indexOf('// Botão vira', start));
  const summary = new Element();
  const modal = new Element('hidden');
  const rows = ['NAO_INFORMADO', 'SEM_PROFESSOR', '42', 'NAO_OFERECIDA'].map(currentId => ({
    querySelectorAll: () => [{ dataset: { currentId } }],
  }));
  const context = vm.createContext({
    window: {}, setSavedState() {},
    document: {
      querySelectorAll: () => rows,
      getElementById: id => id === 'allocSavedSummary' ? summary : modal,
    },
  });
  vm.runInContext(source, context);
  context.window.openAllocSavedModal();
  assert.equal(summary.textContent, '2 de 4 disciplinas com docente definido. 2 ainda sem docente.');
  assert.equal(modal.classList.contains('hidden'), false);
});
