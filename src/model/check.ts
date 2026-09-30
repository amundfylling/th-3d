// Tiny typed runtime-check combinators. A Check<T> both validates unknown JSON and, through its
// type parameter, lets tsc verify that a runtime schema matches the TypeScript interface.

export type Check<T> = (value: unknown, path: string, errors: string[]) => value is T;

const OPTIONAL = Symbol("optional");
export interface OptionalCheck<T> {
  [OPTIONAL]: true;
  check: Check<T>;
}

type Shape = Record<string, Check<unknown> | OptionalCheck<unknown>>;
type CheckedType<C> = C extends Check<infer T> ? T : C extends OptionalCheck<infer T> ? T : never;
type RequiredKeys<S extends Shape> = { [K in keyof S]: S[K] extends OptionalCheck<unknown> ? never : K }[keyof S];
type OptionalKeys<S extends Shape> = Exclude<keyof S, RequiredKeys<S>>;
type Simplify<T> = { [K in keyof T]: T[K] };
export type ObjectOf<S extends Shape> = Simplify<
  { [K in RequiredKeys<S>]: CheckedType<S[K]> } & { [K in OptionalKeys<S>]?: CheckedType<S[K]> }
>;

const fail = (errors: string[], path: string, message: string): false => {
  errors.push(`${path}: ${message}`);
  return false;
};

export const str: Check<string> = (v, p, e): v is string => typeof v === "string" || fail(e, p, "expected string");

export const nonEmptyStr: Check<string> = (v, p, e): v is string =>
  (typeof v === "string" && v.length > 0) || fail(e, p, "expected non-empty string");

export const num: Check<number> = (v, p, e): v is number =>
  (typeof v === "number" && Number.isFinite(v)) || fail(e, p, "expected finite number");

export const bool: Check<boolean> = (v, p, e): v is boolean => typeof v === "boolean" || fail(e, p, "expected boolean");

export const nul: Check<null> = (v, p, e): v is null => v === null || fail(e, p, "expected null");

export function lit<const L extends readonly (string | number | boolean)[]>(...values: L): Check<L[number]> {
  return (v, p, e): v is L[number] =>
    values.includes(v as L[number]) || fail(e, p, `expected one of ${JSON.stringify(values)}, got ${JSON.stringify(v)}`);
}

export function nullable<T>(inner: Check<T>): Check<T | null> {
  return (v, p, e): v is T | null => v === null || inner(v, p, e);
}

export function arr<T>(item: Check<T>): Check<T[]> {
  return (v, p, e): v is T[] => {
    if (!Array.isArray(v)) return fail(e, p, "expected array");
    let ok = true;
    v.forEach((x, i) => {
      if (!item(x, `${p}[${i}]`, e)) ok = false;
    });
    return ok;
  };
}

export function tuple<const C extends readonly Check<unknown>[]>(
  ...items: C
): Check<{ -readonly [K in keyof C]: CheckedType<C[K]> }> {
  return (v, p, e): v is { -readonly [K in keyof C]: CheckedType<C[K]> } => {
    if (!Array.isArray(v) || v.length !== items.length) return fail(e, p, `expected tuple of length ${items.length}`);
    let ok = true;
    items.forEach((check, i) => {
      if (!check(v[i], `${p}[${i}]`, e)) ok = false;
    });
    return ok;
  };
}

/** Accepts the first alternative that validates; reports all alternatives' errors if none does. */
export function union<A, B>(a: Check<A>, b: Check<B>): Check<A | B> {
  return (v, p, e): v is A | B => {
    const ea: string[] = [];
    if (a(v, p, ea)) return true;
    const eb: string[] = [];
    if (b(v, p, eb)) return true;
    e.push(`${p}: no alternative matched`, ...ea.map((m) => `  ${m}`), ...eb.map((m) => `  ${m}`));
    return false;
  };
}

export function opt<T>(check: Check<T>): OptionalCheck<T> {
  return { [OPTIONAL]: true, check };
}

/** Object with exactly the listed keys (unknown keys are rejected to catch typos). */
export function obj<S extends Shape>(shape: S): Check<ObjectOf<S>> {
  return (v, p, e): v is ObjectOf<S> => {
    if (typeof v !== "object" || v === null || Array.isArray(v)) return fail(e, p, "expected object");
    const record = v as Record<string, unknown>;
    let ok = true;
    for (const key of Object.keys(record)) {
      if (!(key in shape)) ok = fail(e, `${p}.${key}`, "unknown key");
    }
    for (const [key, entry] of Object.entries(shape)) {
      const isOptional = OPTIONAL in entry;
      const check = isOptional ? (entry as OptionalCheck<unknown>).check : (entry as Check<unknown>);
      if (!(key in record)) {
        if (!isOptional) ok = fail(e, `${p}.${key}`, "missing required key");
        continue;
      }
      if (!check(record[key], `${p}.${key}`, e)) ok = false;
    }
    return ok;
  };
}
