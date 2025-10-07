import fs from 'fs-extra';
import path from 'path';
import { exec } from 'child_process';
import { GoogleGenerativeAI } from '@google/generative-ai';
import 'dotenv/config';

// --- Configuration ---
const STATE_FILE = path.resolve('agent/state/context.json');
const LOGS_DIR = path.resolve('logs');
const PROMPTS_DIR = path.resolve('agent/prompts');

// --- State Management ---
async function readState() {
  try {
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

// --- Real LLM Call using Gemini ---
export async function callLLM(promptName, context) {
    if (!process.env.GEMINI_API_KEY) {
        throw new Error("GEMINI_API_KEY is not set. Please create a .env file and add it.");
    }

    const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);
    const model = genAI.getGenerativeModel({ model: "gemini-1.5-flash-latest" });

    const promptTemplatePath = path.join(PROMPTS_DIR, `${promptName}.prompt.md`);
    const promptTemplate = await fs.readFile(promptTemplatePath, 'utf-8');
    
    const populatedPrompt = promptTemplate.replace('{{context}}', JSON.stringify(context, null, 2));

    console.log(`--- Calling Gemini for ${promptName} phase ---`);
    const result = await model.generateContent(populatedPrompt);
    const response = await result.response;
    const text = await response.text();
    console.log(`--- Gemini response received ---`);

    // Clean the response to extract only the JSON part
    const jsonMatch = text.match(/```json\n([\s\S]*?)\n```/);
    if (!jsonMatch || !jsonMatch[1]) {
        console.error("LLM response did not contain a valid JSON block:", text);
        throw new Error("LLM returned invalid data format.");
    }

    try {
        return JSON.parse(jsonMatch[1]);
    } catch (e) {
        console.error("Failed to parse JSON from LLM response:", jsonMatch[1]);
        throw new Error("LLM returned invalid JSON.");
    }
}


// --- Tool Execution ---
export function runTool(toolScript) {
    return new Promise((resolve, reject) => {
        const command = `node "${path.resolve('agent/tools', toolScript)}"`;
        exec(command, (error, stdout, stderr) => {
            if (error) {
                console.error(`Error executing ${toolScript}:`, stderr);
                reject(new Error(stderr || 'Unknown error during tool execution'));
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
          result = await callLLM('plan', context);
          break;
        case 'do':
          result = await callLLM('execute', state);
          break;
        case 'reflect':
          try {
            await runTool('linter.js');
            await runTool('tester.js');
            result = await callLLM('reflect', state);
          } catch (error) {
            errorSummary = error.message || JSON.stringify(error);
            finalStatus = 'failed';
            
            const iteration = {
              id: iterationId, phase, timestamp: new Date().toISOString(), summary: `Failed ${phase} phase.`,
              status: finalStatus, errorSummary, output: result
            };
            state.iterations.push(iteration);
            state.current = { ...state.current, status: finalStatus, error: errorSummary };
            
            await writeState(state);
            throw error;
          }
          break;
        case 'repair':
          result = await callLLM('repair', state);
          break;
        default:
          throw new Error(`Unknown phase: ${phase}`);
      }

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
        if (!errorSummary) {
            errorSummary = error.message || JSON.stringify(error);
            state.current.status = 'failed';
            state.current.error = errorSummary;
            await writeState(state);
        }
        throw error;
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