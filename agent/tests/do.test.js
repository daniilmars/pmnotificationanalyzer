import { describe, it, expect, jest, beforeEach, afterAll } from '@jest/globals';
import fs from 'fs-extra';
import path from 'path';
import Agent from '../agent.js';

const STATE_FILE = path.resolve('agent/state/context.json');

jest.mock('../agent.js', () => {
    const originalModule = jest.requireActual('../agent.js');
    const mockLLMCall = async (promptName, context) => {
        if (promptName === 'execute') {
            return (await import('./fixtures/do-response.json', { assert: { type: 'json' } })).default;
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

describe('DO Phase', () => {
    beforeEach(async () => {
        await fs.ensureDir(path.dirname(STATE_FILE));
        await fs.writeJson(STATE_FILE, {
            iterations: [{ id: 1, phase: 'think', status: 'completed', output: { tasks: ['...'] } }],
            current: { phase: 'think', iteration: 1, status: 'completed' }
        });
    });

    afterAll(async () => {
        await fs.remove(STATE_FILE);
    });

    it('should generate files and update the state', async () => {
        const agent = new Agent();
        await agent.runPhase('do');

        const state = await fs.readJson(STATE_FILE);

        expect(state.iterations).toHaveLength(2);
        const doIteration = state.iterations[1];

        expect(doIteration.phase).toBe('do');
        expect(doIteration.status).toBe('completed');
        expect(doIteration.output.files).toBeInstanceOf(Array);
        expect(doIteration.output.files[0].path).toBe('backend/app/services/scoring_service.py');
    });
});