import { readFileSync, writeFileSync, renameSync } from 'node:fs';
import { randomBytes } from 'node:crypto';
import { join, isAbsolute } from 'node:path';
import { ViewerError, ID, digest, questionDigest } from './model.mjs';
import { validAnswer } from './answer.mjs';

const corrupt = (file) => new ViewerError('corrupt_state', `Invalid saved state in ${file}.`, 'Preserve the file for recovery, move it aside, then reopen the original MDX source.');
export function readJSON(file) {
  try { return JSON.parse(readFileSync(file, 'utf8')); }
  catch (error) {
    if (error.code === 'ENOENT') return null;
    if (error instanceof SyntaxError) throw corrupt(file);
    throw error;
  }
}
export function atomicJSON(file, data) {
  const tmp = `${file}.${process.pid}.${randomBytes(24).toString('hex')}.tmp`;
  writeFileSync(tmp, `${JSON.stringify(data)}\n`, { mode: 0o600, flag: 'wx' });
  renameSync(tmp, file);
}
export const documentPath = (root, id) => join(root, 'documents', `${id}.json`);
export function readDocument(root, id) {
  const file = documentPath(root, id);
  const value = readJSON(file);
  if (!value) throw Object.assign(new ViewerError('document_not_found', `No published document "${id}".`, 'Run open with the original source MDX path.'), { status: 404 });
  if (typeof value.sourcePath !== 'string' || !isAbsolute(value.sourcePath) || typeof value.source !== 'string' || typeof value.publishedAt !== 'string' || !Number.isFinite(Date.parse(value.publishedAt))) throw corrupt(file);
  const { document } = value;
  if (!document || document.version !== 1 || document.docId !== id || document.revision !== digest(value.source) ||
    typeof document.title !== 'string' || !document.title.trim() || !['plan', 'recap'].includes(document.kind) ||
    !Array.isArray(document.blocks) || document.blocks.some((block) => !block || typeof block !== 'object' || typeof block.type !== 'string')) throw corrupt(file);
  const questions = document.blocks.filter((block) => block.type === 'component' && block.name === 'Question');
  if (new Set(questions.map((question) => question.id)).size !== questions.length || questions.some((question) =>
    !ID.test(question.id ?? '') || !question.data || typeof question.data.prompt !== 'string' ||
    (question.data.options !== undefined && (!Array.isArray(question.data.options) || question.data.options.some((option) => typeof option !== 'string'))) ||
    question.questionDigest !== questionDigest(question.data))) throw corrupt(file);
  return value;
}
export function readAnswers(root, id) {
  const file = join(root, 'answers', `${id}.json`);
  const answers = readJSON(file) ?? {};
  if (typeof answers !== 'object' || Array.isArray(answers) || Object.entries(answers).some(([blockId, answer]) =>
    !ID.test(blockId) || !answer || !validAnswer(answer.value) || !/^[a-f0-9]{64}$/.test(answer.digest ?? '') ||
    typeof answer.savedAt !== 'string' || !Number.isFinite(Date.parse(answer.savedAt)) ||
    Object.keys(answer).some((key) => !['value', 'digest', 'savedAt'].includes(key)))) throw corrupt(file);
  return answers;
}
export function answersFor(root, id) {
  const { document } = readDocument(root, id);
  return {
    ok: true, docId: id, revision: document.revision,
    answers: Object.entries(readAnswers(root, id)).map(([blockId, answer]) => {
      const question = document.blocks.find((block) => block.type === 'component' && block.name === 'Question' && block.id === blockId);
      const stale = !question || answer.digest !== question.questionDigest;
      return { blockId, ...answer, stale, active: !stale, removed: !question };
    }),
  };
}
