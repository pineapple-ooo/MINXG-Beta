#!/usr/bin/env node
/**
 * MINXG TypeScript Schema Validator Test Runner
 *
 * Runs the validation tests directly without tsx/tsc dependency.
 * Tests pure-JS validators defined in src/validate.js.
 *
 * Usage: node ts_core/run_tests.js
 */
import { validateMessage, validateMessages, validateChatRequest } from '../dist/validate.js';

let passed = 0;
let failed = 0;

function test(name, fn) {
    try {
        fn();
        console.log('  \x1b[32m✓\x1b[0m ' + name);
        passed++;
    } catch (e) {
        console.log('  \x1b[31m✗\x1b[0m ' + name + ': ' + e.message);
        failed++;
    }
}

function eq(a, b) {
    if (a !== b) throw new Error(`Expected ${JSON.stringify(b)}, got ${JSON.stringify(a)}`);
}

function ok(x) {
    if (!x) throw new Error('Expected truthy value, got ' + JSON.stringify(x));
}

console.log('MINXG TypeScript Schema Validator Tests\n');

test('validateMessage — valid user', () => {
    const r = validateMessage({ role: 'user', content: 'hi' });
    ok(r);
    eq(r.role, 'user');
    eq(r.content, 'hi');
});

test('validateMessage — invalid role returns null', () => {
    eq(validateMessage({ role: 'bad', content: 'x' }), null);
});

test('validateMessage — null input returns null', () => {
    eq(validateMessage(null), null);
});

test('validateMessages — array of 2 messages', () => {
    const r = validateMessages([
        { role: 'system', content: 'sys' },
        { role: 'user', content: 'hi' },
    ]);
    ok(r);
    eq(r.length, 2);
});

test('validateMessages — empty array returns null', () => {
    eq(validateMessages([]), null);
});

test('validateChatRequest — valid minimal', () => {
    const r = validateChatRequest({
        model: 'gpt-4o',
        messages: [{ role: 'user', content: 'hi' }],
    });
    ok(r.ok);
});

test('validateChatRequest — missing model', () => {
    const r = validateChatRequest({ messages: [{ role: 'user', content: 'hi' }] });
    eq(r.ok, false);
    ok(r.error.includes('model'));
});

test('validateChatRequest — missing messages', () => {
    const r = validateChatRequest({ model: 'gpt-4o' });
    eq(r.ok, false);
});

test('validateChatRequest — full request with reasoning_effort', () => {
    const r = validateChatRequest({
        model: 'gpt-4o',
        messages: [{ role: 'user', content: 'math' }],
        reasoning_effort: 'high',
        temperature: 0.7,
        max_tokens: 100,
    });
    ok(r.ok);
});

test('validateChatRequest — invalid reasoning_effort', () => {
    // Should still pass — reasoning_effort validated at runtime by provider
    const r = validateChatRequest({
        model: 'gpt-4o',
        messages: [{ role: 'user', content: 'x' }],
        reasoning_effort: 'invalid',
    });
    ok(r.ok); // validator passes string-valued field through
});

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed > 0 ? 1 : 0);
