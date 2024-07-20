<script setup>
import ViewBlock from "@/components/ViewBlock.vue";
</script>

<template>
  <ViewBlock class="info-block">
    <template #title>{{ $t('routes.info') }}</template>
    <p>
      Lorem ipsum dolor sit amet, consectetur adipisicing elit. Eligendi illum iure libero tenetur. Ad aliquid assumenda beatae commodi cupiditate
      dolorem ea eos eveniet facere harum, impedit in ipsam ipsum itaque iure iusto labore magnam, neque nulla omnis optio possimus praesentium
      quaerat recusandae repellat repellendus repudiandae saepe sequi tempora, totam ut veritatis voluptate voluptatibus? Aliquam aperiam cum eum
      magni molestiae odio quo repellendus ullam vero! Accusantium amet architecto asperiores consequatur cumque dicta dignissimos, distinctio eaque
      fugiat illo iure magni nisi, numquam obcaecati odit quas qui quibusdam quisquam quos rem sapiente sit tempora voluptatem. Ab adipisci architecto
      aut consequuntur cupiditate dignissimos dolores ea eaque eligendi excepturi exercitationem inventore iusto magni mollitia nemo nobis nulla odio
      officia omnis porro provident quae quia quisquam quod ratione reiciendis rerum saepe sapiente sequi tempora tempore unde velit veniam,
      voluptatem voluptates voluptatibus voluptatum. Doloribus eligendi ex hic laudantium quia sed tenetur totam vero. Alias aliquid aspernatur dicta
      inventore laudantium libero nulla pariatur qui sequi voluptatibus. Ad qui sed unde ut voluptatibus? Architecto aspernatur esse, harum ipsum iste
      maiores molestiae mollitia neque nobis, non odio officiis placeat, quis repellat similique sunt voluptates. Aperiam cumque ducimus est ex hic
      ipsa ipsam nemo obcaecati, pariatur possimus quod repellendus sed sint voluptatem voluptates. Eaque id illo modi mollitia officiis pariatur
      tempore. Accusamus ad asperiores, autem ducimus eius facere in neque nisi perspiciatis quae quia rem reprehenderit velit vero voluptate.
      Accusantium adipisci cumque dolor, eligendi error esse eum iure iusto laudantium, nihil nostrum quidem, quo reiciendis repellendus similique sit
      tempore vel voluptas!
    </p>
    <p>
      Lorem ipsum dolor sit amet, consectetur adipisicing elit. Debitis dolorum error facere fuga magnam, natus suscipit tempora vero. Alias aliquid
      autem deserunt dicta dignissimos distinctio dolorem, dolorum ea earum eligendi explicabo facilis illo impedit inventore ipsam iste itaque
      laborum minus nemo nisi nostrum nulla numquam quae quasi quibusdam quis quo ratione reiciendis rem repudiandae rerum vel vero, vitae. A
      blanditiis cupiditate deserunt, maiores maxime quasi repellat tempore vero. Accusantium deserunt eos id totam. Ad architecto asperiores
      aspernatur consequatur cumque dolor dolores et ex fuga fugiat hic illum, iure laboriosam maiores maxime neque numquam odio, officia officiis
      placeat provident quaerat quod repellendus saepe sequi ullam ut voluptatibus? A aperiam atque corporis dicta, et harum illo laboriosam nesciunt
      quia quidem saepe veniam voluptate, voluptatibus. Aliquid assumenda dolor ea fugiat ipsa iusto maiores non pariatur? Aut consectetur deserunt
      dolores eligendi eum facere laboriosam libero maiores molestias nam natus necessitatibus, numquam, officia quo voluptatum?
    </p>
  </ViewBlock>
</template>

<style scoped lang="scss">
.info-block {
  p:not(:last-child) {
    margin-bottom: 25px;
  }
}
</style>