// Shared subject labels and symbols. Unknown names remain intact.
const subjects = [
 // Sprachen tragen ihre Flagge; Englisch und Erdkunde waren beide ein Globus,
 // Spanisch eine Sonne.
 ['Mathematik','📐',['ma','mathe','mathematik']], ['Deutsch','🇩🇪',['de','deutsch']],
 ['Englisch','🇬🇧',['en','englisch']], ['Spanisch','🇪🇸',['sn','spanisch']],
 ['Französisch','🇫🇷',['fr','französisch','franzoesisch']],
 ['Latein','🏛️',['la','latein']], ['Physik','💡',['ph','physik']],
 ['Chemie','🧪',['ch','chemie']], ['Biologie','🌿',['bi','biologie']],
 ['Politik','🗳️',['po','politik']], ['Geschichte','⏳',['ge','geschichte']],
 ['Erdkunde','🌍',['ek','erdkunde']], ['Werte und Normen','🤝',['wn','wun','werte und normen']],
 ['Sport','🏅',['sp','sport']], ['Musik','🎵',['mu','musik']], ['Kunst','🎨',['ku','kunst']],
];
export function subjectStyle(value) {
 const text = String(value || '').trim();
 const match = subjects.find(s => s[2].includes(text.toLocaleLowerCase('de-DE')));
 return match ? {name:match[0],emoji:match[1]} : {name:text === text.toUpperCase() ? text.charAt(0)+text.slice(1).toLowerCase() : text,emoji:'📚'};
}
