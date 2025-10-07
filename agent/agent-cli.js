#!/usr/bin/env node
import yargs from 'yargs';
import { hideBin } from 'yargs/helpers';
import chalk from 'chalk';
import Agent from './agent.js';
import fs from 'fs-extra';
import path from 'path';

const STATE_FILE = path.resolve('agent/state/context.json');

const agent = new Agent();

// CLI UX Helpers
const phaseColor = {
  think: chalk.blueBright,
  do: chalk.green,
  reflect: chalk.magenta,
  repair: chalk.yellow,
};

function printPhase(phase, message) {
  const color = phaseColor[phase] || chalk.white;
  const icon = {
    think: '🧠',
    do: '🚀',
    reflect: '🧐',
    repair: '🔧',
  }[phase] || '⚙️';
  console.log(color(`${icon} ${phase.toUpperCase()} phase: ${message}`));
}

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
    try {
      printPhase(argv.phase, 'started...');
      await agent.runPhase(argv.phase, { goal: argv.goal });
      printPhase(argv.phase, chalk.green('completed successfully!'));
    } catch (error) {
      printPhase(argv.phase, chalk.red(`failed. Reason: ${error.message}`));
      process.exit(1);
    }
  })
  .command('state <action>', 'Manage agent state', (yargs) => {
    return yargs.positional('action', {
        describe: 'Action to perform on the state',
        choices: ['show', 'reset']
    });
  }, async (argv) => {
      if (argv.action === 'show') {
          const state = await fs.readJson(STATE_FILE, { throws: false }) || {};
          console.log(JSON.stringify(state, null, 2));
      } else if (argv.action === 'reset') {
          await fs.writeJson(STATE_FILE, { iterations: [], current: {} }, { spaces: 2 });
          console.log(chalk.yellow('Agent state has been reset.'));
      }
  })
  .demandCommand(1, 'You need to specify a command.')
  .help()
  .argv;
