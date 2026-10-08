// Optional compatibility check against a separately checked-out pi-subagents.
// Usage: node --experimental-strip-types tests/verify_pi_agents.mjs /path/to/pi-subagents
import { readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import assert from 'node:assert/strict';
if (!process.argv[2]) throw new Error('Pass a pi-subagents source checkout');
const upstream = resolve(process.argv[2]);
const { parseFrontmatter, parseFrontmatterList } = await import(
  pathToFileURL(resolve(upstream, 'src/agents/frontmatter.ts')).href);
const { buildRuntimeName } = await import(
  pathToFileURL(resolve(upstream, 'src/agents/identity.ts')).href);
const agentsDir = new URL('../agents/pi/', import.meta.url);
const files = readdirSync(agentsDir).filter(file => file.endsWith('.md'));
assert.equal(files.length, 5);
for (const file of files) {
  const { frontmatter: f, body } = parseFrontmatter(readFileSync(new URL(file, agentsDir), 'utf8'));
  assert.equal(buildRuntimeName(f.name, f.package), 'hybrid-conductor.' + file.slice(0, -3));
  assert.deepEqual(parseFrontmatterList(f.extensions), []);
  assert.equal(f.defaultContext, 'fresh');
  assert.equal(f.inheritProjectContext, 'true');
  assert.equal(f.inheritGlobalContext, 'false');
  assert.equal(f.inheritSkills, 'false');
  assert.equal(f.model, undefined);
  assert.equal(f.memory, undefined);
  assert.ok(body.length > 0);
  if (f.name === 'reviewer') {
    assert.deepEqual(parseFrontmatterList(f.tools), ['read', 'grep', 'find', 'ls']);
  }
}
console.log('Native pi-subagents parser: all five Agent definitions passed.');
