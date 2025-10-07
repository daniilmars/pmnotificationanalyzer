import { describe, it, expect, jest, beforeEach, afterAll } from '@jest/globals';
import fs from 'fs-extra';
import Agent from '../agent.js';

// Mock the LLM call to return a predefined fixture
jest.mock('../agent.js', () => {
    const originalModule = jest.requireActual('../agent.js');
    return {
        __esModule: true,
        ...originalModule,
        default: class MockAgent extends originalModule.default {
            async runPhase(phase, context) {
                if (phase === 'think') {
                    const thinkResponse = require('./fixtures/think-response.json');
                    const state = await this.readState();
                    state.iterations.push({
                        id: 1,
                        phase: 'think',
                        timestamp: new Date().toISOString(),
                        output: thinkResponse,
                        status: 'completed'
                    });
                    state.current = { phase: 'think', iteration: 1, status: 'completed' };
                    await this.writeState(state);
                    return state;
                }
                return super.runPhase(phase, context);
            }
        }
    };
});

describe('THINK Phase', () => {
    const STATE_FILE = './agent/state/context.json';

    beforeEach(async () => {
        // Ensure a clean state before each test
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
        expect(thinkIteration.output.goal).toBe('Implement user authentication feature');
        expect(thinkIteration.output.tasks).toBeInstanceOf(Array);
        expect(thinkIteration.output.tasks.length).toBeGreaterThan(0);
    });
});
