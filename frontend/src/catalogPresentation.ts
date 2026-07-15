const apiValueLabels: Record<string, string> = {
  academy: 'Академия',
  institute: 'Институт',
  conservatory: 'Консерватория',
  military_academy: 'Военная академия',
  university: 'Университет',
  other: 'Другое',
  state: 'Государственный',
  private: 'Частный',
  mixed: 'Смешанная форма',
  unknown: 'Не указано',
  online: 'Онлайн-мониторинг',
  partial: 'Частичный мониторинг',
  periodic: 'Периодическое обновление',
  reference_only: 'Справочная карточка',
  unsupported: 'Мониторинг не поддерживается',
  broken: 'Мониторинг нарушен',
  needs_review: 'Требует дополнительной проверки',
  full_time: 'Дневная форма',
  part_time: 'Заочная форма',
  distance: 'Дистанционная форма',
  evening: 'Вечерняя форма',
  budget: 'Бюджет',
  paid: 'Платная',
  targeted: 'Целевое обучение',
  separate_competition: 'Отдельный конкурс',
}

const sourceTypeLabels: Record<string, string> = {
  official_registry: 'Официальный реестр',
  official_site: 'Официальный сайт',
  admissions: 'Страница для абитуриентов',
  admission_xml: 'Данные приёмной кампании',
}

export const apiValueLabel = (value: string) => apiValueLabels[value]
  ?? value.replaceAll('_', ' ').replace(/^./u, (letter) => letter.toUpperCase())

export const sourceTypeLabel = (value: string) => sourceTypeLabels[value]
  ?? apiValueLabel(value)

const dateFormatter = new Intl.DateTimeFormat('ru-BY', {
  day: 'numeric',
  month: 'long',
  year: 'numeric',
  timeZone: 'Europe/Minsk',
})

export function formatCatalogDate(value: string | null) {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : dateFormatter.format(date)
}
