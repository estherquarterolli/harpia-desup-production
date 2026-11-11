const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.resolve(__dirname, '../../static/js/support.js'), 'utf8');
const key = 'harpia.support.position.v1';

function target() {
    const listeners = new Map();
    return {
        addEventListener(type, listener) {
            if (!listeners.has(type)) listeners.set(type, []);
            listeners.get(type).push(listener);
        },
        emit(type, data = {}) {
            const event = {
                type, pointerType: 'mouse', pointerId: 1, button: 0, detail: 1,
                clientX: 0, clientY: 0, defaultPrevented: false,
                preventDefault() { this.defaultPrevented = true; },
                stopImmediatePropagation() {},
                ...data,
            };
            for (const listener of listeners.get(type) || []) listener(event);
            return event;
        },
    };
}

function page(options = {}) {
    const window = Object.assign(target(), { innerWidth: 1000, innerHeight: 800 });
    const link = target();
    const captures = new Set();
    link.setPointerCapture = id => captures.add(id);
    link.hasPointerCapture = id => captures.has(id);
    link.releasePointerCapture = id => {
        captures.delete(id);
        link.emit('lostpointercapture', { pointerId: id });
    };
    const classes = new Set();
    const dock = {
        style: {}, offsetWidth: 40, offsetHeight: 112,
        classList: {
            add: name => classes.add(name),
            remove: name => classes.delete(name),
            contains: name => classes.has(name),
        },
        querySelector: () => link,
        getBoundingClientRect() {
            return {
                left: this.style.left ? parseFloat(this.style.left) : window.innerWidth - 40,
                top: this.style.top ? parseFloat(this.style.top) : window.innerHeight - 128,
            };
        },
    };
    const storage = new Map(options.saved ? [[key, options.saved]] : []);
    const timers = [];
    vm.runInNewContext(source, {
        window,
        document: {
            body: {}, getElementById: () => dock,
            querySelector: () => null, querySelectorAll: () => [],
        },
        localStorage: {
            getItem(name) {
                if (options.blockStorage) throw new Error('Storage blocked');
                return storage.get(name) ?? null;
            },
            setItem(name, value) {
                if (options.blockStorage) throw new Error('Storage blocked');
                storage.set(name, value);
            },
        },
        MutationObserver: class { observe() {} },
        setTimeout: callback => timers.push(callback),
    });
    return {
        window, link, dock, storage,
        flushTimers() { timers.splice(0).forEach(callback => callback()); },
        dragTo(x, y, end = 'pointerup') {
            const rect = dock.getBoundingClientRect();
            link.emit('pointerdown', { clientX: rect.left + 20, clientY: rect.top + 20 });
            window.emit('pointermove', { clientX: x, clientY: y });
            window.emit(end);
        },
    };
}

test('clique simples e pequenos movimentos continuam abrindo o suporte', () => {
    const p = page();
    p.link.emit('pointerdown', { clientX: 980, clientY: 700 });
    p.window.emit('pointermove', { clientX: 982, clientY: 701 });
    p.window.emit('pointerup');
    assert.equal(p.link.emit('click').defaultPrevented, false);
    assert.equal(p.storage.size, 0);
    assert.equal(p.dock.style.left, undefined);
});

test('arraste fica dentro da tela, salva posição e não abre o formulário', () => {
    const p = page();
    p.dragTo(-200, -200);
    assert.equal(p.dock.style.left, '0px');
    assert.equal(p.dock.style.top, '0px');
    assert.deepEqual(JSON.parse(p.storage.get(key)), { x: 0, y: 0 });
    assert.equal(p.link.emit('click').defaultPrevented, true);
    p.flushTimers();
    assert.equal(p.link.emit('click').defaultPrevented, false);
    p.dragTo(3000, 3000);
    assert.equal(p.dock.style.left, '960px');
    assert.equal(p.dock.style.top, '688px');
});

test('posição é restaurada ao navegar e se adapta a uma janela menor', () => {
    const p = page({ saved: JSON.stringify({ x: 0.5, y: 0.25 }) });
    assert.equal(p.dock.style.left, '480px');
    assert.equal(p.dock.style.top, '172px');
    p.window.innerWidth = 300;
    p.window.innerHeight = 240;
    p.window.emit('resize');
    assert.equal(p.dock.style.left, '130px');
    assert.equal(p.dock.style.top, '32px');
});

test('dados salvos inválidos mantêm a posição padrão', () => {
    for (const saved of ['{invalid', '{"x":999,"y":1}', '{"x":"0.5","y":1}']) {
        const p = page({ saved });
        assert.equal(p.dock.style.left, undefined);
    }
});

test('armazenamento bloqueado não impede arraste nem clique por teclado', () => {
    const p = page({ blockStorage: true });
    p.dragTo(300, 300);
    assert.equal(p.dock.style.left, '280px');
    assert.equal(p.dock.style.top, '280px');
    assert.equal(p.link.emit('click', { detail: 0 }).defaultPrevented, false);
});

test('cancelamento limpa o arraste e não bloqueia o próximo clique', () => {
    const p = page();
    p.dragTo(300, 300, 'pointercancel');
    assert.equal(p.dock.classList.contains('is-dragging'), false);
    assert.equal(p.link.emit('click').defaultPrevented, false);
});

test('toque e clique com modificadores preservam o comportamento do link', () => {
    for (const data of [{ pointerType: 'touch' }, { ctrlKey: true }, { button: 2 }]) {
        const p = page();
        p.link.emit('pointerdown', data);
        p.window.emit('pointermove', { clientX: 300, clientY: 300 });
        p.window.emit('pointerup');
        assert.equal(p.dock.style.left, undefined);
        assert.equal(p.link.emit('click').defaultPrevented, false);
    }
});
