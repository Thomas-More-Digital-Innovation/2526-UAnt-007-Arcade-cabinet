<template>
  <q-card>
    <q-card-section class="flex items-center justify-between">
      <div class="text-h6">{{ title }}</div>
      <q-btn color="primary" icon="science" label="Test" :href="`${api.defaults.baseURL}/games/${props.id}/test`" :target="'_blank'" />
    </q-card-section>
    <q-card-section class="flex gap-2 justify-end">
      <q-btn color="primary" icon="edit" unelevated :ripple="false" label="Edit" @click="onEdit" />
      <q-btn
        color="negative"
        icon="delete"
        unelevated
        :ripple="false"
        label="Remove"
        @click="onRemove"
      />
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">

import { api } from 'boot/axios';

const props = defineProps<{
  title: string;
  id: string;
  modal: { name: string };
}>();
const emit = defineEmits(['edit', 'update:modal', 'delete']);

function onEdit() {
  emit('edit', props.title);
}

function onRemove() {
  emit('delete', props.title);
}


</script>
