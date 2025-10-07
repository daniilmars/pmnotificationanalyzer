import { describe, test, expect, jest, beforeEach, afterAll } from '@jest/globals';
import fs from 'fs-extra';
import path from 'path';

// 1. Mock child_process BEFORE importing Agent
await jest.unstable_mockModule('child_process', () => ({
  exec: jest.fn((cmd, cb) => cb(null, 'stdout', '')),
}));

// 2. Now import Agent
const { default: Agent } = await import('../agent.js');

// 3. Import the mocked child_process to access exec
const { exec } = await import('child_process');

const STATE_FILE = path.resolve('agent/state/context.json');
const LOGS_DIR = path.resolve('logs');

describe('Agent Integration Test', () => {
  let agent;

  beforeEach(async () => {
    agent = new Agent();
    await fs.ensureDir(path.dirname(STATE_FILE));
    await fs.writeJson(STATE_FILE, { iterations: [], current: {} });
    await fs.ensureDir(LOGS_DIR);
    jest.clearAllMocks();
  });

  afterAll(async () => {
    await fs.remove(LOGS_DIR);
    await fs.remove(STATE_FILE);
  });

  test('should run a full THINK -> DO -> REFLECT (fail) -> REPAIR cycle', async () => {
    // 1. THINK & DO succeed
    await agent.runPhase('think', { goal: 'Integration test goal' });
    await agent.runPhase('do');

    // 2. REFLECT fails via exec mock
    exec.mockImplementationOnce((command, callback) => {
      callback(new Error('Simulated test failure'), '', 'Simulated test failure');
    });

    await expect(agent.runPhase('reflect')).rejects.toThrow('Simulated test failure');

    // 3. REPAIR succeeds - explicitly call it after the failure
    exec.mockImplementation((cmd, cb) => cb(null, 'stdout', ''));
    await agent.runPhase('repair');

    // 4. Validate final state
    const finalState = await fs.readJson(STATE_FILE);
    expect(finalState.iterations.map(it => it.phase)).toEqual(['think', 'do', 'reflect', 'repair']);
    
    const reflectIteration = finalState.iterations[2];
    expect(reflectIteration.status).toBe('failed');
    expect(reflectIteration.errorSummary).toBe('Simulated test failure');

    const repairIteration = finalState.iterations[3];
    expect(repairIteration.status).toBe('completed');
    
    expect(finalState.current.status).toBe('completed');
  });
});
