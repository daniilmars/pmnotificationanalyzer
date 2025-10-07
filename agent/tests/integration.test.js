import { describe, it, expect, jest, beforeEach, afterAll } from '@jest/globals';
import fs from 'fs-extra';
import Agent from '../agent.js';

// This integration test uses a more complex mock to simulate a full cycle
jest.mock('../agent.js', () => {
    const originalModule = jest.requireActual('../agent.js');
    return {
        __esModule: true,
        ...originalModule,
        default: class MockAgent extends originalModule.default {
            async runPhase(phase, context) {
                const state = await this.readState();
                const nextId = state.iterations.length + 1;
                let output = {};
                let status = 'completed';
                let errorSummary = null;

                switch (phase) {
                    case 'think': output = require('./fixtures/think-response.json'); break;
                    case 'do': output = require('./fixtures/do-response.json'); break;
                    case 'reflect':
                        // Simulate a failure in the reflect phase to trigger repair
                        status = 'failed';
                        errorSummary = 'Simulated test failure during reflection';
                        output = {};
                        break;
                    case 'repair': output = require('./fixtures/repair-response.json'); break;
                }

                state.iterations.push({ id: nextId, phase, timestamp: new Date().toISOString(), output, status, errorSummary });
                state.current = { phase, iteration: nextId, status, error: errorSummary };
                
                await this.writeState(state);
                if (errorSummary) throw new Error(errorSummary);
                return state;
            }
        }
    };
});

describe('Agent Integration Test', () => {
    const STATE_FILE = './agent/state/context.json';
    const LOGS_DIR = './logs';

    beforeEach(async () => {
        await fs.ensureDir(LOGS_DIR);
        await fs.writeJson(STATE_FILE, { iterations: [], current: {} });
    });

    afterAll(async () => {
        await fs.remove(STATE_FILE);
        await fs.remove(LOGS_DIR);
    });

    it('should run a full THINK -> DO -> REFLECT (fail) -> REPAIR cycle', async () => {
        const agent = new Agent();

        // 1. THINK phase
        await agent.runPhase('think', { goal: 'Integration test goal' });
        let state = await fs.readJson(STATE_FILE);
        expect(state.iterations[0].phase).toBe('think');
        expect(state.current.phase).toBe('think');

        // 2. DO phase
        await agent.runPhase('do');
        state = await fs.readJson(STATE_FILE);
        expect(state.iterations[1].phase).toBe('do');
        expect(state.current.phase).toBe('do');

        // 3. REFLECT phase (will be mocked to fail)
        await expect(agent.runPhase('reflect')).rejects.toThrow('Simulated test failure during reflection');
        state = await fs.readJson(STATE_FILE);
        expect(state.iterations[2].phase).toBe('reflect');
        expect(state.iterations[2].status).toBe('failed');
        expect(state.current.status).toBe('failed');

        // 4. REPAIR phase
        await agent.runPhase('repair');
        state = await fs.readJson(STATE_FILE);
        expect(state.iterations[3].phase).toBe('repair');
        expect(state.current.phase).toBe('repair');
        expect(state.current.status).toBe('completed');

        // Final check
        expect(state.iterations).toHaveLength(4);
    });
});
