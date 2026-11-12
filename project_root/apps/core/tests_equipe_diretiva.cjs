const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.resolve(__dirname, '../../static/js/equipe-diretiva.js'), 'utf8');

function formFixture(value = 'TODOS') {
    const events = {};
    const selection = {value};
    const checklist = {
        hidden: false,
        classList: {toggle(name, hidden) { checklist.hidden = hidden; }},
    };
    const group = {querySelector: () => selection};
    const button = {disabled: false};
    const error = {scrollIntoView() { error.scrolled = true; }};
    const fields = {innerHTML: '', querySelector: () => error};
    const form = {
        action: '/ocupacao/salvar/', dataset: {},
        addEventListener(name, handler) { events[name] = handler; },
        querySelector(selector) {
            return {
                'fieldset[data-abrangencia-cursos]': group,
                '[data-cursos-especificos]': checklist,
                '[data-ocupacao-campos]': fields,
                'button[type="submit"]': button,
            }[selector] || null;
        },
    };
    return {form, selection, checklist, fields, button, events};
}

function start(forms, fetch) {
    const navigation = [];
    vm.runInNewContext(source, {
        document: {querySelectorAll: () => forms.map(item => item.form)},
        window: {location: {assign: url => navigation.push(url)}},
        FormData: class {constructor(form) {this.form = form;}},
        fetch,
    });
    return navigation;
}

test('todos/específicos alterna apenas a lista do próprio formulário, sem enviar', () => {
    const novo = formFixture();
    const editar = formFixture('ESPECIFICOS');
    start([novo, editar], () => assert.fail('A escolha de cursos não pode enviar o formulário'));
    assert.equal(novo.checklist.hidden, true);
    assert.equal(editar.checklist.hidden, false);
    novo.selection.value = 'ESPECIFICOS';
    novo.events.change();
    assert.equal(novo.checklist.hidden, false);
    editar.selection.value = 'TODOS';
    editar.events.change();
    assert.equal(editar.checklist.hidden, true);
    assert.equal(novo.checklist.hidden, false);
});

test('erro de validação permanece no modal e permite reenviar com sucesso', async () => {
    const item = formFixture('ESPECIFICOS');
    let requests = 0;
    const navigation = start([item], async (url, options) => {
        requests++;
        assert.equal(url, item.form.action);
        assert.equal(options.method, 'POST');
        assert.equal(options.headers['X-Requested-With'], 'XMLHttpRequest');
        assert.equal(options.body.form, item.form);
        return requests === 1
            ? {ok: false, status: 422, json: async () => ({html: 'Erro de cursos e valores preservados'})}
            : {ok: true, status: 200, json: async () => ({redirect_url: '/equipe-diretiva/'})};
    });
    let prevented = 0;
    const event = {preventDefault() { prevented++; }};
    await item.events.submit(event);
    assert.equal(navigation.length, 0);
    assert.equal(item.fields.innerHTML, 'Erro de cursos e valores preservados');
    assert.equal(item.checklist.hidden, false);
    assert.equal(item.button.disabled, false);
    await item.events.submit(event);
    assert.deepEqual(navigation, ['/equipe-diretiva/']);
    assert.equal(prevented, 2);
});

test('clique duplo não duplica o envio e libera o botão após finalizar', async () => {
    const item = formFixture();
    let finish;
    let requests = 0;
    start([item], () => {
        requests++;
        return new Promise(resolve => {finish = resolve;});
    });
    const event = {preventDefault() {}};
    const first = item.events.submit(event);
    assert.equal(item.button.disabled, true);
    await item.events.submit(event);
    assert.equal(requests, 1);
    finish({ok: true, status: 200, json: async () => ({redirect_url: '/equipe-diretiva/'})});
    await first;
    assert.equal(item.button.disabled, false);
    assert.equal(item.form.dataset.salvando, undefined);
});
