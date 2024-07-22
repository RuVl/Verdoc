<script setup>
import CrossIcon from "@/components/icons/IconCross.vue";

const is_opened = defineModel('is_opened', {default: true});
</script>

<template>
<teleport to="#app">
  <div class="modal-window-wrapper" v-if="is_opened">
    <div class="modal-window">
      <div class="close-icon-container" @click="is_opened=false">
        <CrossIcon class="close-icon"/>
      </div>
      <h2 class="title"><slot name="title"/></h2>
      <slot/>
    </div>
  </div>
</teleport>
</template>

<style scoped lang="scss">
.modal-window-wrapper {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  right: 0;

  display: flex;
  justify-content: center;
  align-items: center;

  background: rgba(0, 0, 0, .25);

  .modal-window {
    position: relative;
    min-height: 200px;
    min-width: 250px;

    background-color: #fff;
    border-radius: 40px;
    padding: 40px 30px;

    display: flex;
    flex-direction: column;

    .title {
      text-align: center;
      margin-bottom: 40px;
    }
  }
}

.close-icon-container {
  $size: 27px;
  width: $size;
  height: $size;

  position: absolute;
  top: 20px;
  right: 20px;

  display: flex;
  justify-content: center;
  align-items: center;

  border-radius: 5px;
  background-color: var(--red-color);

  &:hover {
    cursor: pointer;
    opacity: .7;
  }

  .close-icon {
    margin: auto;
    width: $size - 7px;
    color: white;
  }
}
</style>