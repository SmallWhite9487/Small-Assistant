(function () {
  "use strict";

  const SETTINGS_KEY = "sa.revision.settings";
  const AUTO_ADVANCE_MS = 1500;

  const state = {
    words: [],
    weights: {},
    initial: 1.0,
    show: "word",
    guess: "meaning",
    answer: "choices",
    word: null,
    answered: false,
    tips: 0,
    stats: { answered: 0, correct: 0, streak: 0 },
    undo: null,
    token: 0,
    options: [],
  };

  const $ = (id) => document.getElementById(id);

  function readSettings() {
    try {
      const saved = JSON.parse(localStorage.getItem(SETTINGS_KEY) || "null");
      if (!saved) return;
      if (saved.show === "word" || saved.show === "reading") state.show = saved.show;
      if (saved.guess === "meaning" || saved.guess === "word") state.guess = saved.guess;
      if (saved.answer === "choices" || saved.answer === "typing") state.answer = saved.answer;
    } catch (error) { /* ignore */ }
  }

  function saveSettings() {
    try {
      localStorage.setItem(SETTINGS_KEY, JSON.stringify({
        show: state.show, guess: state.guess, answer: state.answer,
      }));
    } catch (error) { /* ignore */ }
  }

  function shuffle(items) {
    for (let index = items.length - 1; index > 0; index -= 1) {
      const swap = Math.floor(Math.random() * (index + 1));
      [items[index], items[swap]] = [items[swap], items[index]];
    }
    return items;
  }

  /* ---- weights ---------------------------------------------------------- */

  function clamp(value) {
    return Math.min(20, Math.max(0.1, value));
  }

  function adjusted(weight, correct) {
    return clamp(weight * (correct ? 0.8 : 1.25));
  }

  /* Only words the user has answered have a stored weight; the rest use a
     derived default (110% of the average) that is never written to disk. */
  function refreshDefault() {
    const values = Object.values(state.weights);
    const average = values.length ? values.reduce((a, b) => a + b, 0) / values.length : 1.0;
    state.initial = values.length ? clamp(average * 1.1) : 1.0;
  }

  function weightOf(word) {
    return word.id in state.weights ? state.weights[word.id] : state.initial;
  }

  async function storeWeight(word, value) {
    state.weights[word.id] = value;
    refreshDefault();
    try {
      await SA.api("/api/weights/" + encodeURIComponent(word.id), {
        method: "PUT",
        body: { weight: value },
      });
    } catch (error) {
      SA.toast("Could not save the weight: " + error.message, "error");
    }
  }

  async function loadWeights() {
    state.weights = {};
    try {
      const data = await SA.api("/api/weights");
      for (const [id, value] of Object.entries(data.weights || {})) {
        const number = Number(value);
        if (Number.isFinite(number) && number > 0) state.weights[id] = number;
      }
    } catch (error) {
      SA.toast("Could not load your weights: " + error.message, "error");
    }
    refreshDefault();
  }

  /* ---- question state --------------------------------------------------- */

  function answerField() {
    if (state.answer === "typing") return "reading";
    return state.guess === "word" ? "word" : "meaning";
  }

  function expectedValue(word) {
    const field = answerField();
    return word[field] || word.word;
  }

  function normalizeKana(text) {
    const folded = String(text).normalize("NFKC").trim();
    let output = "";
    for (const character of folded) {
      const code = character.codePointAt(0);
      output += code >= 0x30a1 && code <= 0x30f6 ? String.fromCodePoint(code - 0x60) : character;
    }
    return output;
  }

  function pickWord() {
    const pool = state.words.filter((word) => !state.word || word.id !== state.word.id);
    const choices = pool.length ? pool : state.words;
    const total = choices.reduce((sum, word) => sum + Math.max(weightOf(word), 0.0001), 0);
    let roll = Math.random() * total;
    for (const word of choices) {
      roll -= Math.max(weightOf(word), 0.0001);
      if (roll <= 0) return word;
    }
    return choices[choices.length - 1];
  }

  function applySettings() {
    for (const button of $("show-group").querySelectorAll("[data-show]")) {
      button.classList.toggle("active", button.dataset.show === state.show);
      button.disabled = state.answer === "typing" || state.guess === "word";
    }
    for (const button of $("guess-group").querySelectorAll("[data-guess]")) {
      button.classList.toggle("active", button.dataset.guess === state.guess);
      button.disabled = state.answer === "typing";
    }
    for (const button of $("answer-group").querySelectorAll("[data-answer]")) {
      button.classList.toggle("active", button.dataset.answer === state.answer);
    }
  }

  function updateStats() {
    const stats = state.stats;
    const accuracy = stats.answered ? Math.floor((stats.correct * 100) / stats.answered) + "%" : "–";
    $("stat-answered").textContent = stats.answered + " answered";
    $("stat-accuracy").textContent = accuracy + " accuracy";
    $("stat-streak").textContent = stats.streak + " streak";
  }

  function updateWeight() {
    if (!state.word) {
      $("quiz-weight").textContent = "";
      return;
    }
    $("quiz-weight").textContent = "Word weight " + weightOf(state.word).toFixed(2) + " · saved for this device";
  }

  function renderPrompt() {
    const word = state.word;
    if (!word) return;
    let text = word.word;
    if (state.answer !== "typing" && (state.show === "reading" || state.guess === "word")) {
      text = word.reading || word.word;
    }
    $("quiz-prompt").textContent = text;
    const link = $("quiz-conjugate");
    link.href = "/conjugation?word=" + encodeURIComponent(word.word);
  }

  function clearAnswers() {
    $("quiz-options").replaceChildren();
    $("quiz-options").hidden = true;
    $("quiz-input-row").hidden = true;
    state.options = [];
    $("quiz-entry").value = "";
    $("quiz-entry").disabled = false;
    $("quiz-check").disabled = false;
  }

  function renderChoices() {
    const word = state.word;
    const field = answerField();
    const correctValue = expectedValue(word);
    const options = [correctValue];
    const seen = new Set(options);
    const others = shuffle(state.words
      .filter((item) => item.id !== word.id)
      .map((item) => item[field] || item.word));
    for (const value of others) {
      if (!seen.has(value)) {
        seen.add(value);
        options.push(value);
      }
      if (options.length === 4) break;
    }
    shuffle(options);

    const wrap = $("quiz-options");
    wrap.hidden = false;
    state.options = [];
    options.forEach((value, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "option";
      button.dataset.value = value;
      const key = document.createElement("span");
      key.className = "key";
      key.textContent = String(index + 1);
      const label = document.createElement("span");
      label.textContent = value;
      button.append(key, label);
      button.addEventListener("click", () => answer(value));
      wrap.append(button);
      state.options.push(button);
    });
  }

  function renderTyping() {
    $("quiz-input-row").hidden = false;
    const entry = $("quiz-entry");
    entry.focus();
    window.setTimeout(() => entry.focus(), 30);
  }

  function renderAnswers() {
    clearAnswers();
    if (state.answer === "typing") {
      renderTyping();
    } else {
      renderChoices();
    }
  }

  function renderQuestion() {
    if (!state.word) return;
    renderPrompt();
    clearAnswers();
    $("quiz-tip").textContent = "";
    const tipButton = $("tip-btn");
    tipButton.disabled = false;
    tipButton.innerHTML = 'Tip <span class="hint">(T)</span>';
    $("quiz-feedback").textContent = "";
    $("quiz-feedback").className = "quiz-feedback";
    $("quiz-actions").hidden = true;
    $("quiz-override").hidden = true;
    renderAnswers();
    updateStats();
    updateWeight();
  }

  function nextQuestion(keepWord) {
    state.token += 1;
    if (!keepWord || !state.word) state.word = pickWord();
    state.answered = false;
    state.tips = 0;
    state.undo = null;
    renderQuestion();
  }

  /* ---- answering -------------------------------------------------------- */

  function showTip() {
    if (state.answered || state.tips >= 2 || !state.word) return;
    const word = state.word;
    state.tips += 1;
    const typing = state.answer === "typing";
    const guessingWord = state.guess === "word" && !typing;
    const hint = typing ? "" : "  (T)";
    if (state.tips === 1) {
      let text;
      if (typing) text = word.meaning;
      else if (guessingWord) text = word.meaning;
      else if (state.show === "reading") text = word.word;
      else text = word.reading || word.word;
      $("quiz-tip").textContent = text;
      const next = typing ? "reading" : guessingWord ? "original" : "meaning";
      $("tip-btn").innerHTML = "More tip: " + next + hint;
    } else {
      let extra;
      if (typing) extra = expectedValue(word);
      else if (guessingWord) extra = word.word;
      else extra = word.meaning;
      $("quiz-tip").textContent = $("quiz-tip").textContent + "  =  " + extra;
      $("tip-btn").innerHTML = "Tip" + hint;
      $("tip-btn").disabled = true;
    }
  }

  function markOptions(chosen, correctValue) {
    for (const button of state.options) {
      if (button.dataset.value === correctValue) button.classList.add("correct");
      else if (button.dataset.value === chosen) button.classList.add("wrong");
      button.disabled = true;
    }
  }

  function scheduleAdvance() {
    const token = state.token;
    window.setTimeout(() => {
      if (token === state.token && !document.hidden) nextQuestion();
    }, AUTO_ADVANCE_MS);
  }

  function answer(chosen) {
    if (state.answered || !state.word) return;
    state.answered = true;
    const word = state.word;
    const field = answerField();
    const expected = expectedValue(word);
    const typing = state.answer === "typing";
    let correct;
    if (typing) {
      const typed = normalizeKana(chosen);
      correct = typed === normalizeKana(expected) || typed === normalizeKana(word.word);
    } else {
      correct = chosen === expected;
    }
    const counted = correct && state.tips < 2;

    $("tip-btn").disabled = true;
    $("quiz-feedback").className = "quiz-feedback";
    if (typing) {
      $("quiz-entry").disabled = true;
      $("quiz-check").disabled = true;
      $("quiz-card").focus();
    } else {
      markOptions(chosen, expected);
    }

    const stats = state.stats;
    state.undo = { weight: weightOf(word), streak: stats.streak };
    stats.answered += 1;
    stats.correct += counted ? 1 : 0;
    stats.streak = counted ? stats.streak + 1 : 0;
    storeWeight(word, adjusted(weightOf(word), counted));
    updateStats();
    updateWeight();

    const reveal = word.word + "（" + word.reading + "） = " + word.meaning;
    if (counted) {
      $("quiz-feedback").textContent = "Correct!  " + reveal;
      $("quiz-feedback").className = "quiz-feedback ok";
      scheduleAdvance();
      return;
    }

    let prefix = correct ? "Correct, but tips were used.  " : "Not quite.  ";
    if (typing && !correct) prefix += "You typed: " + chosen + "\n";
    $("quiz-feedback").textContent = prefix + reveal;
    $("quiz-feedback").className = "quiz-feedback bad";
    $("quiz-actions").hidden = false;
    $("quiz-override").hidden = !(typing && !correct && state.tips < 2);
  }

  function submitTyped() {
    const entry = $("quiz-entry");
    if (state.answered || entry.disabled) return;
    const value = entry.value.trim();
    if (value) answer(value);
  }

  function override() {
    if (!state.undo || !state.answered || !state.word) return;
    const stats = state.stats;
    const { weight, streak } = state.undo;
    state.undo = null;
    stats.correct += 1;
    stats.streak = streak + 1;
    storeWeight(state.word, adjusted(weight, true));
    updateStats();
    updateWeight();
    $("quiz-actions").hidden = true;
    $("quiz-feedback").textContent = "Marked as correct.  " + state.word.word + "（" + state.word.reading + "） = " + state.word.meaning;
    $("quiz-feedback").className = "quiz-feedback ok";
    scheduleAdvance();
  }

  async function resetWeights() {
    const ok = await SA.confirm({
      title: "Reset every weight?",
      message: "Your saved weights on this device are cleared and every word goes back to the default. This cannot be undone.",
      confirmText: "Reset weights",
    });
    if (!ok) return;
    try {
      await SA.api("/api/weights", { method: "DELETE" });
    } catch (error) {
      SA.toast("Could not reset the weights: " + error.message, "error");
      return;
    }
    state.weights = {};
    refreshDefault();
    updateWeight();
    SA.toast("All weights are back to 1.");
  }

  /* ---- wiring ----------------------------------------------------------- */

  $("show-group").addEventListener("click", (event) => {
    const button = event.target.closest("[data-show]");
    if (!button || button.dataset.show === state.show) return;
    state.show = button.dataset.show;
    saveSettings();
    applySettings();
    renderPrompt();
  });

  function retarget() {
    saveSettings();
    applySettings();
    if (state.word) nextQuestion(true);
  }

  $("guess-group").addEventListener("click", (event) => {
    const button = event.target.closest("[data-guess]");
    if (!button || button.dataset.guess === state.guess) return;
    state.guess = button.dataset.guess;
    retarget();
  });

  $("answer-group").addEventListener("click", (event) => {
    const button = event.target.closest("[data-answer]");
    if (!button || button.dataset.answer === state.answer) return;
    state.answer = button.dataset.answer;
    retarget();
  });

  $("tip-btn").addEventListener("click", showTip);
  $("quiz-next").addEventListener("click", () => nextQuestion());
  $("quiz-override").addEventListener("click", override);
  $("quiz-check").addEventListener("click", submitTyped);
  $("quiz-entry").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      submitTyped();
    }
  });
  $("reset-weights").addEventListener("click", resetWeights);

  document.addEventListener("keydown", (event) => {
    if (document.querySelector("dialog[open]") || event.metaKey || event.ctrlKey || event.altKey) return;
    const key = event.key;
    const entry = $("quiz-entry");
    const inEntry = event.target === entry;

    if (key === "t" || key === "T") {
      if (!inEntry) {
        event.preventDefault();
        showTip();
      }
      return;
    }

    if (!state.answered && !inEntry && /^[1-4]$/.test(key)) {
      const option = state.options[Number(key) - 1];
      if (option) {
        event.preventDefault();
        option.click();
      }
      return;
    }

    if ((key === " " || key === "Enter") && state.answered && !$("quiz-actions").hidden) {
      if (event.target.closest("button, a") && event.target !== $("quiz-next")) return;
      event.preventDefault();
      nextQuestion();
    }
  });

  async function init() {
    readSettings();
    applySettings();
    try {
      const data = await SA.api("/api/words");
      state.words = data.words;
    } catch (error) {
      SA.toast(error.message, "error");
    }
    if (state.words.length < 2) {
      $("quiz-toolbar").hidden = true;
      $("quiz-card").hidden = true;
      $("reset-weights").hidden = true;
      $("revision-empty").hidden = false;
      return;
    }
    await loadWeights();
    nextQuestion();
  }

  init();
})();
