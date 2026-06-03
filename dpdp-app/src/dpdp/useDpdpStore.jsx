import { createContext, useContext, useReducer } from 'react';

const DpdpContext = createContext(null);

/* Read devMode from localStorage on startup so it survives refreshes */
const _storedDevMode = typeof window !== 'undefined'
  ? localStorage.getItem('devMode') === 'true'
  : false;

const initialState = {
  isProcess: null,       // true | false
  processType: '',       // string
  selectedPiis: [],      // string[]
  customPiis: [],        // string[]
  imageIds: [],          // number[] — DB image IDs to run OCR against
  devMode: _storedDevMode,  // boolean — developer mode toggle
  selectedBaseline: null,   // { id, file_name } — baseline selected for comparison
};

function reducer(state, action) {
  switch (action.type) {
    case 'SET_IS_PROCESS':
      return { ...state, isProcess: action.payload, processType: action.payload ? state.processType : '' };
    case 'SET_PROCESS_TYPE':
      return { ...state, processType: action.payload };
    case 'SET_IMAGE_IDS':
      return { ...state, imageIds: action.payload };
    case 'TOGGLE_PII':
      return {
        ...state,
        selectedPiis: state.selectedPiis.includes(action.payload)
          ? state.selectedPiis.filter(p => p !== action.payload)
          : [...state.selectedPiis, action.payload],
      };
    case 'ADD_CUSTOM_PII':
      if (!action.payload.trim() || state.customPiis.includes(action.payload.trim())) return state;
      return { ...state, customPiis: [...state.customPiis, action.payload.trim()], selectedPiis: [...state.selectedPiis, action.payload.trim()] };
    case 'REMOVE_CUSTOM_PII':
      return {
        ...state,
        customPiis: state.customPiis.filter(p => p !== action.payload),
        selectedPiis: state.selectedPiis.filter(p => p !== action.payload),
      };
    // Bulk: add all items in payload that aren't already selected (no duplicates)
    case 'SELECT_MANY': {
      const toAdd = action.payload.filter(p => !state.selectedPiis.includes(p));
      return { ...state, selectedPiis: [...state.selectedPiis, ...toAdd] };
    }
    // Bulk: remove all items in payload from selectedPiis
    case 'DESELECT_MANY':
      return { ...state, selectedPiis: state.selectedPiis.filter(p => !action.payload.includes(p)) };
    // Clear ALL selected (built-in + custom selections, but keep customPiis list)
    case 'CLEAR_ALL':
      return { ...state, selectedPiis: [], customPiis: [] };
    case 'SET_DEV_MODE': {
      const next = Boolean(action.payload);
      localStorage.setItem('devMode', String(next));
      return { ...state, devMode: next };
    }
    case 'SELECTED_BASELINE':
      return { ...state, selectedBaseline: action.payload }; // { id, file_name } or null
    case 'RESET':
      return { ...initialState, devMode: state.devMode, selectedBaseline: state.selectedBaseline };  // preserve devMode + selectedBaseline across RESET
    default:
      return state;
  }
}

export function DpdpProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  return (
    <DpdpContext.Provider value={{ state, dispatch }}>
      {children}
    </DpdpContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useDpdpStore() {
  const ctx = useContext(DpdpContext);
  if (!ctx) throw new Error('useDpdpStore must be used within DpdpProvider');
  return ctx;
}
