/*
	* Copyright (C) 2020-2021  Yomichan Authors
	*
	* This program is free software: you can redistribute it and/or modify
	* it under the terms of the GNU General Public License as published by
	* the Free Software Foundation, either version 3 of the License, or
	* (at your option) any later version.
	*
	* This program is distributed in the hope that it will be useful,
	* but WITHOUT ANY WARRANTY; without even the implied warranty of
	* MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
	* GNU General Public License for more details.
	*
	* You should have received a copy of the GNU General Public License
	* along with this program.  If not, see <https://www.gnu.org/licenses/>.
	*/

/*
	* From Yomichan /ext/js/language/sandbox/japanese-util.js
	* Accessed: 2021/11/03 (c1a51ae41f77558a281b5d34ad1527049b68bd59)
	* Modifications:
	*  - Removed all code unrelated to distributeFurigana
	*  - Made JapanseUtil static
	*/

var JapaneseUtil = (() => {
	const KATAKANA_SMALL_KA_CODE_POINT = 0x30f5;
	const KATAKANA_SMALL_KE_CODE_POINT = 0x30f6;
	const KANA_PROLONGED_SOUND_MARK_CODE_POINT = 0x30fc;

	const HIRAGANA_RANGE = [0x3040, 0x309f];
	const KATAKANA_RANGE = [0x30a0, 0x30ff];

	const HIRAGANA_CONVERSION_RANGE = [0x3041, 0x3096];
	const KATAKANA_CONVERSION_RANGE = [0x30a1, 0x30f6];

	const KANA_RANGES = [HIRAGANA_RANGE, KATAKANA_RANGE];

	const VOWEL_TO_KANA_MAPPING = new Map([
		[
			'a',
			'ぁあかがさざただなはばぱまゃやらゎわヵァアカガサザタダナハバパマャヤラヮワヵヷ',
		],
		['i', 'ぃいきぎしじちぢにひびぴみりゐィイキギシジチヂニヒビピミリヰヸ'],
		[
			'u',
			'ぅうくぐすずっつづぬふぶぷむゅゆるゥウクグスズッツヅヌフブプムュユルヴ',
		],
		[
			'e',
			'ぇえけげせぜてでねへべぺめれゑヶェエケゲセゼテデネヘベペメレヱヶヹ',
		],
		[
			'o',
			'ぉおこごそぞとどのほぼぽもょよろをォオコゴソゾトドノホボポモョヨロヲヺ',
		],
		['', 'のノ'],
	]);

	const KANA_TO_VOWEL_MAPPING = (() => {
		const map = new Map();
		for (const [vowel, characters] of VOWEL_TO_KANA_MAPPING) {
			for (const character of characters) {
				map.set(character, vowel);
			}
		}
		return map;
	})();

	function isCodePointInRange(codePoint, [min, max]) {
		return codePoint >= min && codePoint <= max;
	}

	function isCodePointInRanges(codePoint, ranges) {
		for (const [min, max] of ranges) {
			if (codePoint >= min && codePoint <= max) {
				return true;
			}
		}
		return false;
	}

	function getProlongedHiragana(previousCharacter) {
		switch (KANA_TO_VOWEL_MAPPING.get(previousCharacter)) {
			case 'a':
				return 'あ';
			case 'i':
				return 'い';
			case 'u':
				return 'う';
			case 'e':
				return 'え';
			case 'o':
				return 'う';
			default:
				return null;
		}
	}

	// eslint-disable-next-line no-shadow
	class JapaneseUtil {
		// Character code testing functions

		isCodePointKana(codePoint) {
			return isCodePointInRanges(codePoint, KANA_RANGES);
		}

		// Conversion functions

		convertKatakanaToHiragana(text, keepProlongedSoundMarks = false) {
			let result = '';
			const offset =
				HIRAGANA_CONVERSION_RANGE[0] - KATAKANA_CONVERSION_RANGE[0];
			for (let char of text) {
				const codePoint = char.codePointAt(0);
				switch (codePoint) {
					case KATAKANA_SMALL_KA_CODE_POINT:
					case KATAKANA_SMALL_KE_CODE_POINT:
						// No change
						break;
					case KANA_PROLONGED_SOUND_MARK_CODE_POINT:
						if (!keepProlongedSoundMarks && result.length > 0) {
							const char2 = getProlongedHiragana(result[result.length - 1]);
							if (char2 !== null) {
								char = char2;
							}
						}
						break;
					default:
						if (isCodePointInRange(codePoint, KATAKANA_CONVERSION_RANGE)) {
							char = String.fromCodePoint(codePoint + offset);
						}
						break;
				}
				result += char;
			}
			return result;
		}

		// Furigana distribution

		distributeFurigana(term, reading) {
			if (reading === term) {
				// Same
				return [this._createFuriganaSegment(term, '')];
			}

			const groups = [];
			let groupPre = null;
			let isKanaPre = null;
			for (const c of term) {
				const codePoint = c.codePointAt(0);
				const isKana = this.isCodePointKana(codePoint);
				if (isKana === isKanaPre) {
					groupPre.text += c;
				} else {
					groupPre = {
						isKana,
						text: c,
						textNormalized: null,
					};
					groups.push(groupPre);
					isKanaPre = isKana;
				}
			}
			for (const group of groups) {
				if (group.isKana) {
					group.textNormalized = this.convertKatakanaToHiragana(group.text);
				}
			}

			const readingNormalized = this.convertKatakanaToHiragana(reading);
			const segments = this._segmentizeFurigana(
				reading,
				readingNormalized,
				groups,
				0,
			);
			if (segments !== null) {
				return segments;
			}

			// Fallback
			return [this._createFuriganaSegment(term, reading)];
		}

		distributeFuriganaHTML(term, reading) {
			const segments = this.distributeFurigana(term, reading);

			const result = ['<ruby>'];
			for (const segment of segments) {
				result.push(segment.text);
				result.push('<rt>');
				result.push(segment.reading);
				result.push('</rt>');
			}
			result.push('</ruby>');

			return result.join('');
		}

		// Private

		_createFuriganaSegment(text, reading) {
			return { text, reading };
		}

		_segmentizeFurigana(reading, readingNormalized, groups, groupsStart) {
			const groupCount = groups.length - groupsStart;
			if (groupCount <= 0) {
				return reading.length === 0 ? [] : null;
			}

			const group = groups[groupsStart];
			const { isKana, text } = group;
			const textLength = text.length;
			if (isKana) {
				const { textNormalized } = group;
				if (readingNormalized.startsWith(textNormalized)) {
					const segments = this._segmentizeFurigana(
						reading.substring(textLength),
						readingNormalized.substring(textLength),
						groups,
						groupsStart + 1,
					);
					if (segments !== null) {
						if (reading.startsWith(text)) {
							segments.unshift(this._createFuriganaSegment(text, ''));
						} else {
							segments.unshift(
								...this._getFuriganaKanaSegments(text, reading),
							);
						}
						return segments;
					}
				}
				return null;
			} else {
				let result = null;
				for (let i = reading.length; i >= textLength; --i) {
					const segments = this._segmentizeFurigana(
						reading.substring(i),
						readingNormalized.substring(i),
						groups,
						groupsStart + 1,
					);
					if (segments !== null) {
						if (result !== null) {
							// More than one way to segmentize the tail; mark as ambiguous
							return null;
						}
						const segmentReading = reading.substring(0, i);
						segments.unshift(
							this._createFuriganaSegment(text, segmentReading),
						);
						result = segments;
					}
					// There is only one way to segmentize the last non-kana group
					if (groupCount === 1) {
						break;
					}
				}
				return result;
			}
		}

		_getFuriganaKanaSegments(text, reading) {
			const textLength = text.length;
			const newSegments = [];
			let start = 0;
			let state = reading[0] === text[0];
			for (let i = 1; i < textLength; ++i) {
				const newState = reading[i] === text[i];
				if (state === newState) {
					continue;
				}
				newSegments.push(
					this._createFuriganaSegment(
						text.substring(start, i),
						state ? '' : reading.substring(start, i),
					),
				);
				state = newState;
				start = i;
			}
			newSegments.push(
				this._createFuriganaSegment(
					text.substring(start, textLength),
					state ? '' : reading.substring(start, textLength),
				),
			);
			return newSegments;
		}
	}

	return new JapaneseUtil();
})();
