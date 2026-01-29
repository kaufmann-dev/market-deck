import {
    updateTagColor, deleteTagColor, addTagColor,
    saveListFromModal, deleteListFromModal,
    saveBaseCurrency,
    saveTicker, deleteTicker, addTicker, retryLoadData, initApp
} from './api.js';

import {
    showHome, switchList, openListEditModal, closeListEditModal,
    openCreateListModal, openEditor, closeEditor, setView
} from './ui.js';

// Expose functions globally for index.html inline event handlers
window.updateTagColor = updateTagColor;
window.deleteTagColor = deleteTagColor;
window.addTagColor = addTagColor;
window.saveListFromModal = saveListFromModal;
window.deleteListFromModal = deleteListFromModal;
window.saveBaseCurrency = saveBaseCurrency;
window.saveTicker = saveTicker;
window.deleteTicker = deleteTicker;
window.addTicker = addTicker;
window.retryLoadData = retryLoadData;

window.showHome = showHome;
window.switchList = switchList;
window.openListEditModal = openListEditModal;
window.closeListEditModal = closeListEditModal;
window.openCreateListModal = openCreateListModal;
window.openEditor = openEditor;
window.closeEditor = closeEditor;
window.setView = setView;

// Start app
initApp();
