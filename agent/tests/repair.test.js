import { describe, it, expect, jest, beforeEach, afterAll } from '@jest/globals';
import fs from 'fs-extra';
import path from 'path';
import Agent from '../agent.js';

const STATE_FILE = path.resolve('agent/state/context.json');

jest.mock('../agent.js', () => {
    const originalModule = jest.requireActual('../agent.js');
    const mockLLMCall = async (promptName, context) => {
        if (promptName === 'repair') {
            return (await import('./fixtures/repair-response.json', { assert: { type: 'json' } })).default;
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

describe('REPAIR Phase', () => {
    beforeEach(async () => {
        await fs.ensureDir(path.dirname(STATE_FILE));
        await fs.writeJson(STATE_FILE, {
            iterations: [
                { id: 1, phase: 'think', status: 'completed' },
                { id: 2, phase: 'do', status: 'completed' },
                { id: 3, phase: 'reflect', status: 'failed', errorSummary: 'Test failed' }
            ],
            current: { phase: 'reflect', iteration: 3, status: 'failed', error: 'Test failed' }
        });
    });

    afterAll(async () => {
        await fs.remove(STATE_FILE);
    });

    it('should generate a repair plan and update the state', async () => {
        const agent = new Agent();
        await agent.runPhase('repair');

        const state = await fs.readJson(STATE_FILE);

        expect(state.iterations).toHaveLength(4);
        const repairIteration = state.iterations[3];

        expect(repairIteration.phase).toBe('repair');
        expect(repairIteration.status).toBe('completed');
        expect(repairIteration.output.analysis).toBeDefined();
        expect(repairIteration.output.fixes).toBeInstanceOf(Array);
    });
});