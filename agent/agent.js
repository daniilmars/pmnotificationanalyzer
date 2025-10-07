import fs from 'fs-extra';
import path from 'path';
import { exec } from 'child_process';

// --- Configuration ---
const STATE_FILE = path.resolve('agent/state/context.json');
const LOGS_DIR = path.resolve('logs');

// --- State Management ---
async function readState() {
  try {
    // Use fs-extra's readJson for robustness
    return await fs.readJson(STATE_FILE);
  } catch (error) {
    if (error.code === 'ENOENT') {
      return { iterations: [], current: { phase: 'idle', iteration: 0 } };
    }
    throw error;
  }
}

async function writeState(newState) {
  const tempFile = `${STATE_FILE}.${Date.now()}.tmp`;
  await fs.writeJson(tempFile, newState, { spaces: 2 });
  await fs.rename(tempFile, STATE_FILE);
}

async function logEvent(phase, data) {
  const date = new Date();
  const yyyy = date.getFullYear();
  const mm = String(date.getMonth() + 1).padStart(2, '0');
  const dd = String(date.getDate()).padStart(2, '0');
  const logDir = path.join(LOGS_DIR, `${yyyy}-${mm}-${dd}`);
  await fs.ensureDir(logDir);

  const logFilePath = path.join(logDir, `${phase}.log`);
  const logEntry = {
    timestamp: date.toISOString(),
    phase,
    ...data,
  };
  await fs.appendFile(logFilePath, JSON.stringify(logEntry) + '\n');
}

// --- Mock LLM Call (Corrected Syntax) ---
async function mockLLMCall(promptName, context) {
  if (promptName === 'plan') {
    return {
      goal: context.goal || "Refactor scoring.py for better accuracy.",
      tasks: ["Analyze current scoring.py", "Implement new algorithm", "Add regression tests"],
      status: "planned",
      "reasoning": "The current implementation is inefficient."
    };
  }
  if (promptName === 'execute') {
    return {
      files: [
        { path: "backend/app/services/scoring_service.py", content: "# Refactored scoring logic...\n" },
        { path: "backend/tests/services/test_scoring_service.py", content: "# New tests for refactored logic...\n" }
      ]
    };
  }
  if (promptName === 'reflect') {
    return {
      insights: ["Refactoring was successful.", "Test coverage increased by 10%."],
      "summary": "Completed the refactoring of the scoring service."
    };
  }
  if (promptName === 'repair') {
    return {
      analysis: "The error was caused by a missing null check.",
      fixes: ["Add a null check in scoring_service.py", "Add a new test case for the null input."]
    };
  }
  return {};
}

// --- Tool Execution (Corrected Command) ---
function runTool(toolScript) {
    return new Promise((resolve, reject) => {
        const command = `node "${path.resolve('agent/tools', toolScript)}"`;
        exec(command, (error, stdout, stderr) => {
            if (error) {
                console.error(`Error executing ${toolScript}:`, stderr);
                reject({ error: stderr, stdout });
            } else {
                resolve(stdout);
            }
        });
    });
}

// --- Agent Class ---
class Agent {
  constructor() {
    this.taskQueue = [];
    this.isRunning = false;
  }

  async runPhase(phase, context) {
    const state = await readState();
    const iterationId = (state.iterations.length || 0) + 1;

    state.current = { phase, iteration: iterationId, status: 'running' };
    await writeState(state);
    await logEvent(phase, { message: `Starting phase for iteration ${iterationId}` });

    let result = {};
    let errorSummary = null;
    let finalStatus = 'completed';

    try {
      switch (phase) {
        case 'think':
          result = await mockLLMCall('plan', context);
          break;
        case 'do':
          result = await mockLLMCall('execute', state);
          break;
        case 'reflect':
          // This block now contains its own error handling, as per the patch
          try {
            await runTool('linter.js');
            await runTool('tester.js');
            result = await mockLLMCall('reflect', state);
          } catch (error) {
            // This is the critical fix: handle the error, set state, save, then rethrow
            errorSummary = error.message || JSON.stringify(error);
            finalStatus = 'failed';
            
            const iteration = {
              id: iterationId, phase, timestamp: new Date().toISOString(), summary: `Failed ${phase} phase.`,
              status: finalStatus, errorSummary, output: result
            };
            state.iterations.push(iteration);
            state.current = { ...state.current, status: finalStatus, error: errorSummary };
            
            await writeState(state); // Persist the failed state
            throw error; // Rethrow for the test harness
          }
          break;
        case 'repair':
          result = await mockLLMCall('repair', state);
          break;
        default:
          throw new Error(`Unknown phase: ${phase}`);
      }

      // Success path: update and save state
      const iteration = {
        id: iterationId, phase, timestamp: new Date().toISOString(), summary: result.summary || `Completed ${phase} phase.`,
        status: finalStatus, errorSummary, output: result
      };
      state.iterations.push(iteration);
      state.current = { ...state.current, status: finalStatus };
      await writeState(state);
      await logEvent(phase, { message: `Phase ${finalStatus}`, result });

      return state;

    } catch (error) {
        // This will now only catch errors from the reflect phase rethrow, or other unexpected errors
        if (!errorSummary) { // Ensure we don't double-handle the reflect error
            errorSummary = error.message || JSON.stringify(error);
            state.current.status = 'failed';
            state.current.error = errorSummary;
            await writeState(state);
        }
        throw error; // Always rethrow to notify the caller/test
    }
  }

  enqueue(phase, context = {}) {
    this.taskQueue.push({ phase, context });
    if (!this.isRunning) {
      this.processQueue();
    }
  }

  async processQueue() {
    if (this.taskQueue.length === 0) {
      this.isRunning = false;
      return;
    }
    this.isRunning = true;
    const { phase, context } = this.taskQueue.shift();
    
    try {
      await this.runPhase(phase, context);
    } catch (error) {
      // Error is already logged
    }
    
    this.processQueue();
  }
}

export default Agent;
