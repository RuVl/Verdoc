<script setup>
import {ref} from "vue";
import DropdownIcon from "@/components/icons/IconDropdown.vue";

const selected_index = defineModel('selected', {type: Number, default: 0});
defineProps({
  elements: Array,
  name: String
});

const is_opened = ref(false);

const selectElement = (index) => {
  selected_index.value = index;
  is_opened.value = false;
};
</script>

<template>
  <div class="dropdown">
    <div class="dropdown-toggle" @click="is_opened=!is_opened">
      <slot :element="elements[selected_index]" name="default"/>
      <DropdownIcon class="caret" :class="{ active: is_opened }"/>
    </div>
    <ul v-if="is_opened" class="dropdown-menu">
      <li v-for="(element, index) in elements" :key="element.name" @click="selectElement(index)">
        <slot :element="element" name="default"/>
      </li>
    </ul>
    <slot :element="elements[selected_index]" name="hidden-input">
      <input type="hidden" :name="name" :value="elements[selected_index]">
    </slot>
  </div>
</template>

<style scoped lang="scss">
.dropdown {
  position: relative;
  user-select: none;
  width: fit-content;

  .dropdown-toggle {
    display: flex;
    align-items: center;
    cursor: pointer;

    width: 260px;
    height: 45px;
    padding: 0 30px;

    border: 0;
    border-radius: 25px;
    box-shadow: 0 0 8px 0 rgba(0, 0, 0, 0.14) inset;

    .caret {
      transition: transform 0.4s;
      width: 20px;
      margin-left: auto;

      &.active {
        transform: rotate(180deg);
      }
    }
  }

  .dropdown-menu {
    $border-radius: 20px;

    position: absolute;
    background-color: #fff;
    border-radius: $border-radius;
    border: 1px solid rgba(0, 0, 0, 0.14);
    box-shadow: 0 0 8px 0 rgba(0, 0, 0, 0.07) inset;
    min-width: 100%;
    z-index: 10;
    margin-top: 3px;
    padding: 0;
    list-style-type: none;

    li {
      height: 45px;
      padding: 0 30px;
      cursor: pointer;
      display: flex;
      align-items: center;

      &:hover {
        opacity: .7;
        background-color: rgba(0,0,0,.025);
      }

      &:first-child {
        border-top-left-radius: $border-radius;
        border-top-right-radius: $border-radius;
      }

      &:last-child {
        border-bottom-left-radius: $border-radius;
        border-bottom-right-radius: $border-radius;
      }
    }

    .dropdown-menu li:hover {
      background-color: #f1f1f1;
    }
  }
}
</style>