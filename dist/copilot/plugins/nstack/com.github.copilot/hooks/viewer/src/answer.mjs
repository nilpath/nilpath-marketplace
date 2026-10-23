export const ANSWER_MAX_LENGTH = 10000;
export const answerSchema = { type: 'string', minLength: 1, maxLength: ANSWER_MAX_LENGTH, pattern: '\\S', description: `Nonblank. The viewer enforces a maximum of ${ANSWER_MAX_LENGTH} UTF-16 code units, as in browser text controls.` };
export const validAnswer = (value) => typeof value === 'string' && value.length <= ANSWER_MAX_LENGTH && /\S/.test(value);
