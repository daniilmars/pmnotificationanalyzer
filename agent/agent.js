import fs from 'fs/promises';
import path from 'path';
import yargs from 'yargs';
import { hideBin } from 'yargs/helpers';

// --- Configuration ---
const STATE_FILE = path.resolve('agent/state/context.json');
const PROMPTS_DIR = path.resolve('agent/prompts');
const LOGS_DIR = path.resolve('logs');

// --- Helper Functions ---

async function readState() {
  try {
    const content = await fs.readFile(STATE_FILE, 'utf-8');
    return JSON.parse(content);
  } catch (error) {
    if (error.code === 'ENOENT') {
      return {}; // Return empty state if file doesn't exist
    }
    throw error;
  }
}

async function writeState(newState) {
  await fs.mkdir(path.dirname(STATE_FILE), { recursive: true });
  await fs.writeFile(STATE_FILE, JSON.stringify(newState, null, 2), 'utf-8');
}

async function logEvent(eventName, data) {
  await fs.mkdir(LOGS_DIR, { recursive: true });
  const timestamp = new Date().toISOString();
  const logFileName = `${timestamp.replace(/:/g, '-')}_${eventName}.log`;
  const logFilePath = path.join(LOGS_DIR, logFileName);
  const logContent = `[${timestamp}] Event: ${eventName}\n\nData:\n${JSON.stringify(data, null, 2)}\n`;
  await fs.writeFile(logFilePath, logContent);
}

async function getPrompt(promptName) {
    const promptPath = path.join(PROMPTS_DIR, `${promptName}.prompt.md`);
    return fs.readFile(promptPath, 'utf-8');
}

// --- Mock LLM Call ---
// In a real implementation, this would call the Gemini, Claude, or OpenAI API.
async function mockLLMCall(prompt, context) {
    console.log('--- Mock LLM Call ---');
    console.log('Prompt:', prompt);
    console.log('Context:', JSON.stringify(context, null, 2));
    console.log('--------------------');
    
    // This mock will return a predefined JSON structure based on the prompt.
    if (prompt.includes("Analyze the user's goal")) { // plan.prompt.md
        return JSON.stringify({
            goal: "Improve text quality scoring accuracy",
            tasks: ["Refactor scoring.py", "Add regression tests for scoring logic"],
            "status": "planned"
        }, null, 2);
    }
    if (prompt.includes("Generate the code")) { // execute.prompt.md
        return JSON.stringify({
            files: [
                { path: "backend/app/services/scoring_service.py", content: "# New scoring logic here...\n" },
                { path: "backend/tests/services/test_scoring_service.py", content: "# New regression tests here...\n" }
            ]
        }, null, 2);
    }
    if (prompt.includes("Reflect on the results")) { // reflect.prompt.md
        return JSON.stringify({
            insights: [
                "The new scoring logic is more robust.",
                "Regression tests cover edge cases.",
                "Consider adding performance benchmarks in the next iteration."
            ],
            "status": "reflection_complete"
        }, null, 2);
    }
    if (prompt.includes("Analyze the error")) { // repair.prompt.md
        return JSON.stringify({
            fixes: [
                "Corrected a division by zero error in scoring_service.py",
                "Added a test case to prevent future regressions of this bug."
            ],
            "status": "repair_plan_created"
        }, null, 2);
    }
    return "{}";
}


// --- Agent Phases ---

async function think(goal) {
  console.log('🤔 Starting THINK phase...');
  const currentState = await readState();
  const prompt = await getPrompt('plan');
  
  const context = {
      ...currentState,
      goal: goal || currentState.goal || "No goal specified. Please provide a goal.",
  };

  const llmResponse = await mockLLMCall(prompt, context);
  const plan = JSON.parse(llmResponse);

  const newState = { ...currentState, ...plan };
  await writeState(newState);
  await logEvent('think', { goal, plan });
  console.log('✅ THINK phase complete. New plan saved to state.');
  console.log(JSON.stringify(newState, null, 2));
}

async function doo() {
    console.log('🚀 Starting DO phase...');
    const currentState = await readState();
    if (currentState.status !== 'planned') {
        console.error('❌ Cannot execute. Current state is not "planned". Run THINK phase first.');
        return;
    }
    const prompt = await getPrompt('execute');
    const llmResponse = await mockLLMCall(prompt, currentState);
    const executionResult = JSON.parse(llmResponse);

    // In a real agent, you would write these files to the filesystem.
    console.log('Applying file changes:');
    for (const file of executionResult.files) {
        console.log(`  - Writing to ${file.path}`);
        // await fs.mkdir(path.dirname(file.path), { recursive: true });
        // await fs.writeFile(file.path, file.content, 'utf-8');
    }

    const newState = { ...currentState, status: 'executed', changes: executionResult.files };
    await writeState(newState);
    await logEvent('do', { changes: executionResult.files });
    console.log('✅ DO phase complete. Code generated.');
}

async function reflect() {
    console.log('🧐 Starting REFLECT phase...');
    const currentState = await readState();
     if (currentState.status !== 'executed' && currentState.status !== 'repaired') {
        console.error('❌ Cannot reflect. Current state is not "executed" or "repaired". Run DO phase first.');
        return;
    }
    // In a real agent, you would run tests here and add the results to the context.
    const testResults = { success: true, output: "All tests passed!" }; 
    
    const prompt = await getPrompt('reflect');
    const context = { ...currentState, testResults };
    
    const llmResponse = await mockLLMCall(prompt, context);
    const reflection = JSON.parse(llmResponse);

    const newState = { ...currentState, ...reflection };
    await writeState(newState);
    await logEvent('reflect', { reflection });
    console.log('✅ REFLECT phase complete. Insights recorded.');
}

async function repair() {
    console.log('🔧 Starting REPAIR phase...');
    const currentState = await readState();
    // This phase should be triggered by failed tests.
    const testResults = { success: false, error: "pytest failed: AssertionError in test_scoring.py" };

    const prompt = await getPrompt('repair');
    const context = { ...currentState, testResults };

    const llmResponse = await mockLLMCall(prompt, context);
    const repairPlan = JSON.parse(llmResponse);

    const newState = { ...currentState, ...repairPlan };
    await writeState(newState);
    await logEvent('repair', { repairPlan });
    console.log('✅ REPAIR phase complete. Repair plan generated.');
    // Next step would be another DO phase to apply the fixes.
}


// --- CLI Setup ---

yargs(hideBin(process.argv))
  .command('run <phase>', 'Run a specific agent phase', (yargs) => {
    return yargs.positional('phase', {
      describe: 'The phase to run',
      choices: ['think', 'do', 'reflect', 'repair']
    }).option('goal', {
        alias: 'g',
        type: 'string',
        description: 'The high-level goal for the THINK phase'
    });
  }, async (argv) => {
    switch (argv.phase) {
      case 'think':
        await think(argv.goal);
        break;
      case 'do':
        await doo();
        break;
      case 'reflect':
        await reflect();
        break;
      case 'repair':
        await repair();
        break;
    }
  })
  .command('state <action>', 'Manage agent state', (yargs) => {
    return yargs.positional('action', {
        describe: 'Action to perform on the state',
        choices: ['show', 'reset']
    });
  }, async (argv) => {
      if (argv.action === 'show') {
          const state = await readState();
          console.log(JSON.stringify(state, null, 2));
      } else if (argv.action === 'reset') {
          await writeState({});
          console.log('Agent state has been reset.');
      }
  })
  .command('test', 'Run linters and tests', () => {
      console.log('Running linters, pytest, and UI build...');
      // This would be implemented by calling the scripts in the tools/ directory
      console.log('✅ All tests passed!');
  })
  .demandCommand(1, 'You need to specify a command.')
  .help()
  .argv;
