<template>
  <q-page class="container mx-auto px-5 md:px-0">
    <div class="flex justify-end mt-10">
      <q-btn
        color="green"
        icon="add"
        label="Add Game"
        unelevated
        :ripple="false"
        @click="confirm = true"
      />
    </div>

    <!-- Game cards -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
      <game-card
        v-for="game in data"
        :key="game.id"
        :title="game.name"
        :modal="modalGame"
        :id="game.id"
        @edit="onEditGame(game)"
        @delete="deleteGame(game)"
      />
    </div>

    <!-- Add/Edit game dialog -->
    <q-dialog v-model="confirm" @hide="resetModal">
      <q-card class="w-120">
        <q-card-section class="row items-center">
          <div class="text-h6">{{ isEditMode ? 'Edit Game' : 'New Game' }}</div>
          <q-space />
          <q-btn icon="close" unelevated v-close-popup />
        </q-card-section>
        <q-card-section>
          <q-input v-model="modalGame.name" type="text" label="Game Name" />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn
            v-if="isEditMode"
            flat
            label="Save"
            color="primary"
            v-close-popup
            @click="updateGame"
          />
          <q-btn v-else flat label="Add" color="green" v-close-popup @click="addGame" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue';
import { useQuasar } from 'quasar';
import GameCard from '../components/GameCard.vue';
import { api } from 'boot/axios';

interface Game {
  id: string;
  name: string;
}

const $q = useQuasar(); 

const data = reactive<Game[]>([]);
const confirm = ref(false);
const isEditMode = ref(false);
const modalGame = reactive<{ id: string | undefined; name: string }>({ id: undefined, name: '' });

function resetModal() {
  confirm.value = false;
  isEditMode.value = false;
  modalGame.id = undefined;
  modalGame.name = '';
}

function addGame() {
  api.post('/games', { name: modalGame.name }).then((response) => {
    const newGame = response.data.game;
    data.push(newGame);
  });
}

function onEditGame(game: Game) {
  modalGame.id = game.id;
  modalGame.name = game.name;
  isEditMode.value = true;
  confirm.value = true;
}

function updateGame() {
  api.put(`/games/${modalGame.id}`, { id: modalGame.id, name: modalGame.name }).then((response) => {
    const updatedGame = response.data.game;
    if (!updatedGame) return;
    const idx = data.findIndex((g) => g.id === updatedGame.id);
    if (idx !== -1 && data[idx]) {
      data[idx].name = updatedGame.name;
    }
  });
}

function deleteGame(params: { id: string }) {
  $q.dialog({
    title: 'Confirm deletion',
    message: 'Are you sure you want to delete this game? This action cannot be undone.',
    cancel: true,
    ok: {
      label: 'Delete',
      color: 'negative',
    },
    
  })
    .onOk(() => {
      api.delete(`/games/${params.id}`).then(() => {
        const idx = data.findIndex((g) => g.id === params.id);
        if (idx !== -1) {
          data.splice(idx, 1);
        }
      });
    })
    .onCancel(() => {
      // console.log('>>>> Cancel')
    })
    .onDismiss(() => {
      // console.log('I am triggered on both OK and Cancel')
    });
}

function loadData() {
  api.get('/games').then((response) => {
    data.splice(0, data.length, ...response.data.games);
  });
}

// Load data on component creation
loadData();
</script>
