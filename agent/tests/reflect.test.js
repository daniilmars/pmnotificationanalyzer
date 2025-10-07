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
                if (phase === 'reflect') {
                    const reflectResponse = require('./fixtures/reflect-response.json');
                    const state = await this.readState();
                    state.iterations.push({
                        id: 3,
                        phase: 'reflect',
                        timestamp: new Date().toISOString(),
                        output: reflectResponse,
                        status: 'completed'
                    });
                    await this.writeState(state);
                    return state;
                }
                return super.runPhase(phase, context);
            }
        }
    };
});

describe('REFLECT Phase', () => {
    const STATE_FILE = './agent/state/context.json';

    beforeEach(async () => {
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
        expect(reflectIteration.output.insights.length).toBeGreaterThan(0);
        expect(reflectIteration.output.summary).toBeDefined();
    });
});
