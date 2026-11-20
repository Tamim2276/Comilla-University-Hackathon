// Placeholder page for the scaffold step. Real pages come in D1-R3.
function App() {
  return (
    <main className="min-h-screen bg-bd-green flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-lg p-8 text-center max-w-sm w-full">
        {/* The flag in miniature: a red disc on green */}
        <div className="mx-auto mb-4 flex h-20 w-28 items-center justify-center rounded-md bg-bd-green">
          <div className="h-11 w-11 rounded-full bg-bd-red" />
        </div>
        <h1 className="text-4xl font-bold text-bd-green">এক কল</h1>
        <p className="mt-2 text-gray-600">Ek Call</p>
        <button
          type="button"
          className="mt-6 min-h-12 w-full rounded-xl bg-bd-red px-6 text-lg font-bold text-white hover:bg-bd-red-dark"
        >
          শুরু করুন
        </button>
        <p className="mt-4 text-sm text-bd-red-dark">Theme check: Bangladesh flag colours.</p>
      </div>
    </main>
  )
}

export default App
