import { describe, it, expect, jest, beforeEach, afterAll } from '@jest/globals';
import fs from 'fs-extra';
import path from 'path';
import Agent from '../agent.js';

const STATE_FILE = path.resolve('agent/state/context.json');

jest.mock('../agent.js', () => {
    const originalModule = jest.requireActual('../agent.js');
    const mockLLMCall = async (promptName, context) => {
        if (promptName === 'reflect') {
            return (await import('./fixtures/reflect-response.json', { assert: { type: 'json' } })).default;
        }
        return originalModule.mockLLMCall(promptName, context);
    };
    return {
        ...originalModule,
        __esModule: true,
        default: class MockAgent extends originalModule.default {
             constructor() {
                super();
                this.runPhase = jest.fn().mockImplementation(originalModule.default.prototype.runPhase);
            }
        },
        mockLLMCall: jest.fn().mockImplementation(mockLLMCall),
    };
});

describe('REFLECT Phase', () => {
    beforeEach(async () => {
        await fs.ensureDir(path.dirname(STATE_FILE));
        await fs.writeJson(STATE_FILE, {
            iterations: [
                { id: 1, phase: 'think', status: 'completed' },
                { id: 2, phase: 'do', status: 'completed' }
            ],
            current: { phase: 'do', iteration: 2, status: 'completed' }
        });
    });

    afterAll(async () => {
        await fs.remove(STATE_FILE);
    });

    it('should generate insights and update the state', async () => {
        const agent = new Agent();
        await agent.runPhase('reflect');

        const state = await fs.readJson(STATE_FILE);

        expect(state.iterations).toHaveLength(3);
        const reflectIteration = state.iterations[2];

        expect(reflectIteration.phase).toBe('reflect');
        expect(reflectIteration.status).toBe('completed');
        expect(reflectIteration.output.insights).toBeInstanceOf(Array);
        expect(reflectIteration.output.summary).toBeDefined();
    });
});