(function () {
  "use strict";

  window.SATagFilter = function (container, onChange) {
    const tags = [];
    let options = [];
    const label = document.createElement("span");
    label.className = "tag-filter-label";
    label.dataset.i18n = "word.part_of_speech";
    label.textContent = SA.t("word.part_of_speech");
    const chips = document.createElement("span");
    chips.className = "tag-filter-chips";
    const add = document.createElement("button");
    add.className = "btn sm tag-filter-add";
    add.type = "button";
    add.textContent = "+";
    add.dataset.i18nAriaLabel = "filter.add_pos";
    add.setAttribute("aria-label", SA.t("filter.add_pos"));
    const menu = document.createElement("div");
    menu.className = "tag-filter-menu";
    menu.hidden = true;
    container.classList.add("tag-filter");
    container.replaceChildren(label, chips, add, menu);

    function render() {
      chips.replaceChildren();
      tags.forEach((tag) => {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "tag-filter-chip";
        chip.textContent = "#." + tag + " ×";
        chip.setAttribute("aria-label", SA.t("filter.remove_pos", { tag }));
        chip.addEventListener("click", () => {
          tags.splice(tags.indexOf(tag), 1);
          render();
          onChange();
        });
        chips.append(chip);
      });
    }

    function addTag(tag) {
      if (!tags.includes(tag)) {
        tags.push(tag);
        render();
        onChange();
      }
    }

    function renderMenu() {
      menu.replaceChildren();
      const available = options.filter((tag) => !tags.includes(tag));
      if (available.length === 0) {
        const empty = document.createElement("span");
        empty.className = "tag-filter-empty";
        empty.textContent = SA.t("filter.no_unused_tags");
        menu.append(empty);
        return;
      }
      available.forEach((tag) => {
        const option = document.createElement("button");
        option.type = "button";
        option.className = "tag-filter-option";
        option.textContent = "#." + tag;
        option.addEventListener("click", () => {
          addTag(tag);
          menu.hidden = true;
        });
        menu.append(option);
      });
    }

    add.addEventListener("click", () => {
      renderMenu();
      menu.hidden = !menu.hidden;
    });

    document.addEventListener("click", (event) => {
      if (!container.contains(event.target)) menu.hidden = true;
    });

    return {
      tags,
      setOptions(words) {
        options = [...new Set(
          words
            .map((word) => (word.part_of_speech || "").trim().toLowerCase())
            .filter(Boolean)
        )].sort();
      },
      matches(word) {
        return tags.length === 0 || tags.includes((word.part_of_speech || "").trim().toLowerCase());
      },
    };
  };
})();
