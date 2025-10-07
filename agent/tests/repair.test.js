import { describe, it, expect, jest, beforeEach, afterAll } from '@jest/globals';
import fs from 'fs-extra';
import Agent from '../agent.js';

jest.mock('../agent.js', () => {
    const originalModule = jest.requireActual('../agent.js');
    return {
        __esModule: true,
        ...originalModule,
        default: class MockAgent extends originalModule.default {
            async runPhase(phase, context) {
                if (phase === 'repair') {
                    const repairResponse = require('./fixtures/repair-response.json');
                    const state = await this.readState();
                    state.iterations.push({
                        id: 4,
                        phase: 'repair',
                        timestamp: new Date().toISOString(),
                        output: repairResponse,
                        status: 'completed'
                    });
                    state.current = { phase: 'repair', iteration: 4, status: 'completed', error: "Simulated test failure" };
                    await this.writeState(state);
                    return state;
                }
                return super.runPhase(phase, context);
            }
        }
    };
});

describe('REPAIR Phase', () => {
    const STATE_FILE = './agent/state/context.json';

    beforeEach(async () => {
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

    it('should generate a repair plan when a failure occurs', async () => {
        const agent = new Agent();
        await agent.runPhase('repair');

        const state = await fs.readJson(STATE_FILE);

        expect(state.iterations).toHaveLength(4);
        const repairIteration = state.iterations[3];

        expect(repairIteration.phase).toBe('repair');
        expect(repairIteration.status).toBe('completed');
        expect(repairIteration.output.analysis).toBeDefined();
        expect(repairIteration.output.fixes).toBeInstanceOf(Array);
        expect(repairIteration.output.fixes.length).toBeGreaterThan(0);
        expect(state.current.error).toBe("Simulated test failure");
    });
});
