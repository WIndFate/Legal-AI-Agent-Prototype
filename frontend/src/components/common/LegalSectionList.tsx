import type { LegalSection } from '../../data/legalContent';
import styles from '../../styles/legal.module.css';

export default function LegalSectionList({ sections }: { sections: LegalSection[] }) {
  return (
    <>
      {sections.map((section) => (
        <section key={section.title} className={styles.legalSection}>
          <h3>{section.title}</h3>
          {section.blocks.map((block, blockIdx) =>
            block.type === 'paragraph' ? (
              <div key={blockIdx}>
                {block.content.map((paragraph, i) => (
                  <p key={i}>{paragraph}</p>
                ))}
              </div>
            ) : (
              <ul key={blockIdx}>
                {block.content.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            ),
          )}
        </section>
      ))}
    </>
  );
}
