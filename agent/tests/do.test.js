import fs from 'fs-extra';
import Agent from '../agent.js';

import { describe, it, expect, jest, beforeEach, afterAll } from '@jest/globals';
import fs from 'fs-extra';
import Agent from '../agent.js';

// Mock the LLM call and file system writes
jest.mock('../agent.js', () => {
    const originalModule = jest.requireActual('../agent.js');
    return {
        __esModule: true,
        ...originalModule,
        default: class MockAgent extends originalModule.default {
            async runPhase(phase, context) {
                if (phase === 'do') {
                    const doResponse = require('./fixtures/do-response.json');
                    const state = await this.readState();
                    state.iterations.push({
                        id: 2,
                        phase: 'do',
                        timestamp: new Date().toISOString(),
                        output: doResponse,
                        status: 'completed'
                    });
                    // Simulate writing files
                    for (const file of doResponse.files) {
                        // In a real test, you might use an in-memory file system
                        // For this example, we just check the intention
                        expect(file.path).toBeDefined();
                        expect(file.content).toBeDefined();
                    }
                    await this.writeState(state);
                    return state;
                }
                return super.runPhase(phase, context);
            }
        }
    };
});

describe('DO Phase', () => {
    const STATE_FILE = './agent/state/context.json';

    beforeEach(async () => {
        // Set up an initial state with a completed 'think' phase
        await fs.writeJson(STATE_FILE, {
            iterations: [{ id: 1, phase: 'think', status: 'completed', output: { tasks: ['...'] } }],
            current: { phase: 'think', iteration: 1, status: 'completed' }
        });
    });

    afterAll(async () => {
        await fs.remove(STATE_FILE);
    });

    it('should generate files based on the plan and update the state', async () => {
        const agent = new Agent();
        await agent.runPhase('do');

        const state = await fs.readJson(STATE_FILE);

        expect(state.iterations).toHaveLength(2);
        const doIteration = state.iterations[1];

        expect(doIteration.phase).toBe('do');
        expect(doIteration.status).toBe('completed');
        expect(doIteration.output.files).toBeInstanceOf(Array);
        expect(doIteration.output.files.length).toBe(2);
        expect(doIteration.output.files[0].path).toBe('backend/app/auth/user_model.py');
    });
});
