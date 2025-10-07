import { describe, it, expect, jest, beforeEach, afterAll } from '@jest/globals';
import fs from 'fs-extra';
import path from 'path';
import Agent from '../agent.js';

const STATE_FILE = path.resolve('agent/state/context.json');

// Mock the mockLLMCall function directly
jest.mock('../agent.js', () => {
    const originalModule = jest.requireActual('../agent.js');
    const mockLLMCall = async (promptName, context) => {
        if (promptName === 'plan') {
            return (await import('./fixtures/think-response.json', { assert: { type: 'json' } })).default;
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

describe('THINK Phase', () => {
    beforeEach(async () => {
        await fs.ensureDir(path.dirname(STATE_FILE));
        await fs.writeJson(STATE_FILE, { iterations: [], current: {} });
    });

    afterAll(async () => {
        // Clean up state file after all tests
        await fs.remove(STATE_FILE);
    });

    it('should create a valid plan and update the state', async () => {
        const agent = new Agent();
        await agent.runPhase('think', { goal: 'Test goal' });

        const state = await fs.readJson(STATE_FILE);

        expect(state.iterations).toHaveLength(1);
        const thinkIteration = state.iterations[0];

        expect(thinkIteration.phase).toBe('think');
        expect(thinkIteration.status).toBe('completed');
        expect(thinkIteration.output.goal).toBe('Test goal');
        expect(thinkIteration.output.tasks).toBeInstanceOf(Array);
    });
});