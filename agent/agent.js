import fs from 'fs-extra';
import path from 'path';
import { exec } from 'child_process';

// --- Configuration ---
const STATE_FILE = path.resolve('agent/state/context.json');
const LOGS_DIR = path.resolve('logs');

// --- State Management ---
async function readState() {
  try {
    const content = await fs.readFile(STATE_FILE, 'utf-8');
    return JSON.parse(content);
  } catch (error) {
    if (error.code === 'ENOENT') {
      // Return a fresh state if the file doesn't exist
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

// --- Mock LLM Call ---
async function mockLLMCall(promptName, context) {
  // In a real implementation, this would call an external LLM API.
  // For this upgrade, the mock returns structures reflecting the new state.
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

// --- Tool Execution ---
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

    try {
      switch (phase) {
        case 'think':
          result = await mockLLMCall('plan', context);
          break;
        case 'do':
          result = await mockLLMCall('execute', state);
          // In a real scenario, you'd apply the file changes here.
          break;
        case 'reflect':
          // The reflect phase now includes running tests and linters.
          await runTool('linter.js');
          await runTool('tester.js');
          result = await mockLLMCall('reflect', state);
          break;
        case 'repair':
          result = await mockLLMCall('repair', state);
          break;
        default:
          throw new Error(`Unknown phase: ${phase}`);
      }
    } catch (error) {
      errorSummary = error.message || JSON.stringify(error);
      state.current.status = 'failed';
      state.current.error = errorSummary;
      // Automatically enqueue a repair task
      this.enqueue('repair');
    }

    // Update state history
    const finalStatus = errorSummary ? 'failed' : 'completed';
    state.iterations.push({
      id: iterationId,
      phase,
      timestamp: new Date().toISOString(),
      summary: result.summary || `Completed ${phase} phase.`, 
      status: finalStatus,
      errorSummary,
      output: result
    });
    state.current.status = finalStatus;
    await writeState(state);
    await logEvent(phase, { message: `Phase ${finalStatus}`, result });
    
    if (errorSummary) throw new Error(errorSummary);
    return state;
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
      // Error is already logged by runPhase. The queue will continue with the repair task.
    }
    
    this.processQueue();
  }
}

export default Agent;